#!/bin/bash

# ECR 이미지 빌드 및 푸시 스크립트
# 이 스크립트는 Docker 이미지를 빌드하고 AWS ECR에 푸시합니다.

set -e  # 에러 발생 시 스크립트 중단

# 스크립트 위치 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 설정 파일 로드
source "$SCRIPT_DIR/config.sh"

# 프로젝트 루트로 이동
cd "$PROJECT_ROOT"

log_step "=== ECR 이미지 빌드 및 푸시 시작 ==="

# 1. 환경 변수 로드
log_step "1. 환경 설정 확인"
load_env
check_aws_cli
check_docker

# 2. ECR 리포지토리 생성 또는 확인
log_step "2. ECR 리포지토리 확인"
if check_ecr_repository; then
    log_info "ECR 리포지토리가 이미 존재합니다: $ECR_REPOSITORY_NAME"
else
    log_info "ECR 리포지토리를 생성합니다: $ECR_REPOSITORY_NAME"
    aws ecr create-repository \
        --repository-name "$ECR_REPOSITORY_NAME" \
        --region "$AWS_REGION" \
        --image-scanning-configuration scanOnPush=true \
        --encryption-configuration encryptionType=AES256 \
        > /dev/null

    log_success "ECR 리포지토리가 생성되었습니다"
fi

# 3. ECR 로그인
log_step "3. ECR 로그인"
aws ecr get-login-password --region "$AWS_REGION" | \
    docker login --username AWS --password-stdin "$ECR_REGISTRY"
log_success "ECR 로그인 완료"

# 4. Docker 이미지 확인
log_step "4. 기존 Docker 이미지 확인"
if docker image inspect "$DOCKER_IMAGE_NAME:$DOCKER_TAG" &> /dev/null; then
    log_success "기존 Docker 이미지를 찾았습니다: $DOCKER_IMAGE_NAME:$DOCKER_TAG"
else
    log_info "기존 이미지가 없습니다. 새로 빌드합니다."

    # Docker 이미지 빌드
    log_info "Docker 이미지를 빌드합니다..."
    docker build -t "$DOCKER_IMAGE_NAME:$DOCKER_TAG" .
    log_success "Docker 이미지 빌드 완료"
fi

# 5. 이미지 태깅
log_step "5. ECR용 이미지 태깅"
TIMESTAMP_TAG=$(date +%Y%m%d-%H%M%S)

# latest 태그
docker tag "$DOCKER_IMAGE_NAME:$DOCKER_TAG" "$ECR_IMAGE_URI:latest"
# 타임스탬프 태그 (롤백용)
docker tag "$DOCKER_IMAGE_NAME:$DOCKER_TAG" "$ECR_IMAGE_URI:$TIMESTAMP_TAG"

log_success "이미지 태깅 완료"
log_info "- Latest: $ECR_IMAGE_URI:latest"
log_info "- Timestamp: $ECR_IMAGE_URI:$TIMESTAMP_TAG"

# 6. ECR에 푸시
log_step "6. ECR에 이미지 푸시"
log_info "latest 태그 푸시 중..."
docker push "$ECR_IMAGE_URI:latest"

log_info "timestamp 태그 푸시 중..."
docker push "$ECR_IMAGE_URI:$TIMESTAMP_TAG"

log_success "ECR 푸시 완료"

# 7. 정리 작업 (로컬 ECR 태그 이미지 삭제)
log_step "7. 로컬 태그 이미지 정리"
docker rmi "$ECR_IMAGE_URI:latest" "$ECR_IMAGE_URI:$TIMESTAMP_TAG" &> /dev/null || true
log_info "로컬 ECR 태그 이미지가 정리되었습니다"

# 8. 결과 출력
log_step "=== ECR 이미지 푸시 완료 ==="
echo ""
log_success "이미지가 성공적으로 ECR에 푸시되었습니다!"
echo ""
echo "📦 ECR Repository: $ECR_REPOSITORY_NAME"
echo "🏷️  Latest Tag: $ECR_IMAGE_URI:latest"
echo "🏷️  Backup Tag: $ECR_IMAGE_URI:$TIMESTAMP_TAG"
echo ""
echo "🔗 ECR Console: https://$AWS_REGION.console.aws.amazon.com/ecr/repositories/private/$AWS_ACCOUNT_ID/$ECR_REPOSITORY_NAME"
echo ""

# 9. ECR 이미지 목록 확인
log_info "ECR에 저장된 이미지 목록:"
aws ecr list-images \
    --repository-name "$ECR_REPOSITORY_NAME" \
    --region "$AWS_REGION" \
    --query 'imageIds[*].[imageTag,imagePushedAt]' \
    --output table

log_success "스크립트 실행 완료! 다음 단계: ./2-setup-infrastructure.sh"