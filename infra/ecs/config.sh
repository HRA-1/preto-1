#!/bin/bash

# AWS ECS 배포 설정 파일
# 이 파일은 모든 배포 스크립트에서 공통으로 사용됩니다.

# 프로젝트 정보
PROJECT_NAME="preto"
APP_NAME="streamlit-app"
ENVIRONMENT="prod"  # dev, staging, prod

# AWS 설정
AWS_REGION="ap-northeast-2"
AWS_ACCOUNT_ID="201023212334"

# ECR 설정
ECR_REPOSITORY_NAME="${PROJECT_NAME}-${APP_NAME}"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECR_IMAGE_URI="${ECR_REGISTRY}/${ECR_REPOSITORY_NAME}"

# Docker 설정
DOCKER_IMAGE_NAME="${PROJECT_NAME}-1"  # 기존 로컬 이미지명
DOCKER_TAG="latest"

# ECS 설정
ECS_CLUSTER_NAME="${PROJECT_NAME}-${APP_NAME}-cluster"
ECS_SERVICE_NAME="${PROJECT_NAME}-${APP_NAME}-service"
ECS_TASK_FAMILY="${PROJECT_NAME}-${APP_NAME}"
ECS_CONTAINER_NAME="${PROJECT_NAME}-${APP_NAME}-container"

# 컴퓨팅 리소스 (고성능 설정)
ECS_CPU="2048"      # 2 vCPU
ECS_MEMORY="8192"   # 8 GB (OOM 방지를 위해 4GB에서 증가)
ECS_DESIRED_COUNT="1"

# 네트워킹
CONTAINER_PORT="8501"
ALB_PORT="80"

# AWS 리소스 이름
VPC_NAME="${PROJECT_NAME}-vpc"
SECURITY_GROUP_NAME="${PROJECT_NAME}-${APP_NAME}-sg"
ALB_NAME="${PROJECT_NAME}-${APP_NAME}-alb"
TARGET_GROUP_NAME="${PROJECT_NAME}-${APP_NAME}-tg"

# IAM 역할
TASK_EXECUTION_ROLE_NAME="ecsTaskExecutionRole"
TASK_ROLE_NAME="ecsTaskRole"

# CloudWatch 로그
LOG_GROUP_NAME="/ecs/${PROJECT_NAME}-${APP_NAME}"
LOG_RETENTION_DAYS="14"

# 색상 코드 (로그 출력용)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 로그 함수들
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${PURPLE}[STEP]${NC} $1"
}

# AWS CLI 설정 확인
check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI가 설치되어 있지 않습니다."
        exit 1
    fi

    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS 인증정보가 설정되어 있지 않습니다."
        exit 1
    fi

    local account_id=$(aws sts get-caller-identity --query Account --output text)
    if [ "$account_id" != "$AWS_ACCOUNT_ID" ]; then
        log_warning "현재 AWS 계정 ($account_id)이 설정된 계정 ($AWS_ACCOUNT_ID)과 다릅니다."
    fi
}

# Docker 설정 확인
check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker가 설치되어 있지 않습니다."
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker 데몬이 실행되고 있지 않습니다."
        exit 1
    fi
}

# 리소스 존재 확인 함수들
check_ecr_repository() {
    aws ecr describe-repositories --repository-names "$ECR_REPOSITORY_NAME" --region "$AWS_REGION" &> /dev/null
}

check_ecs_cluster() {
    aws ecs describe-clusters --clusters "$ECS_CLUSTER_NAME" --region "$AWS_REGION" \
        --query 'clusters[0].status' --output text 2>/dev/null | grep -q "ACTIVE"
}

check_ecs_service() {
    local service_status=$(aws ecs describe-services --cluster "$ECS_CLUSTER_NAME" --services "$ECS_SERVICE_NAME" --region "$AWS_REGION" \
        --query 'services[0].status' --output text 2>/dev/null)

    # ACTIVE 상태인 경우에만 true 반환
    if [ "$service_status" = "ACTIVE" ]; then
        return 0
    else
        return 1
    fi
}

# 환경 변수 로드
load_env() {
    if [ -f "../../.env" ]; then
        log_info ".env 파일에서 환경 변수를 로드합니다."
        export $(grep -v '^#' ../../.env | xargs)
    else
        log_warning ".env 파일을 찾을 수 없습니다. AWS 자격증명이 다른 방법으로 설정되어 있는지 확인하세요."
    fi
}

# 스크립트 실행 시 기본 체크
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    # 직접 실행된 경우 설정 정보 출력
    echo "=== AWS ECS 배포 설정 ==="
    echo "프로젝트: $PROJECT_NAME"
    echo "애플리케이션: $APP_NAME"
    echo "환경: $ENVIRONMENT"
    echo "AWS 리전: $AWS_REGION"
    echo "AWS 계정 ID: $AWS_ACCOUNT_ID"
    echo "ECR Repository: $ECR_REPOSITORY_NAME"
    echo "ECS 클러스터: $ECS_CLUSTER_NAME"
    echo "ECS 서비스: $ECS_SERVICE_NAME"
    echo "=========================="
fi