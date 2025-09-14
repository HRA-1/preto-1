#!/bin/bash

# AWS ECS 리소스 정리 스크립트
# 이 스크립트는 배포된 모든 AWS 리소스를 안전하게 삭제합니다.

set -e  # 에러 발생 시 스크립트 중단

# 스크립트 위치 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 설정 파일 로드
source "$SCRIPT_DIR/config.sh"

# 사용법 출력
usage() {
    echo "사용법: $0 [OPTIONS]"
    echo ""
    echo "옵션:"
    echo "  --all              모든 리소스 삭제 (기본값)"
    echo "  --service-only     ECS 서비스만 삭제 (인프라 유지)"
    echo "  --keep-ecr         ECR 이미지/리포지토리 유지"
    echo "  --keep-logs        CloudWatch 로그 유지"
    echo "  --dry-run          삭제할 리소스 목록만 출력 (실제 삭제 안함)"
    echo "  --force            확인 없이 바로 삭제"
    echo "  -h, --help         도움말 출력"
    echo ""
    echo "예시:"
    echo "  $0                 # 전체 리소스 삭제 (확인 후)"
    echo "  $0 --force         # 확인 없이 전체 삭제"
    echo "  $0 --service-only  # ECS 서비스만 삭제"
    echo "  $0 --dry-run       # 삭제 예정 리소스 확인"
}

# 기본 설정
DELETE_ALL=true
DELETE_SERVICE_ONLY=false
KEEP_ECR=false
KEEP_LOGS=false
DRY_RUN=false
FORCE=false

# 명령행 인수 파싱
while [[ $# -gt 0 ]]; do
    case $1 in
        --all)
            DELETE_ALL=true
            shift
            ;;
        --service-only)
            DELETE_SERVICE_ONLY=true
            DELETE_ALL=false
            shift
            ;;
        --keep-ecr)
            KEEP_ECR=true
            shift
            ;;
        --keep-logs)
            KEEP_LOGS=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log_error "알 수 없는 옵션: $1"
            usage
            exit 1
            ;;
    esac
done

log_step "=== AWS ECS 리소스 정리 시작 ==="

# 1. 환경 설정 확인
log_step "1. 환경 설정 확인"
load_env
check_aws_cli

# 2. 인프라 정보 로드 (있는 경우)
INFRA_INFO_EXISTS=false
if [ -f "$SCRIPT_DIR/infrastructure.env" ]; then
    source "$SCRIPT_DIR/infrastructure.env"
    INFRA_INFO_EXISTS=true
    log_info "인프라 정보 파일 로드: infrastructure.env"
else
    log_warning "인프라 정보 파일이 없습니다. 설정 파일의 기본값을 사용합니다."
fi

# 3. 현재 존재하는 리소스 확인
log_step "3. 현재 리소스 상태 확인"

# 리소스 존재 여부 확인 함수들
check_resource_exists() {
    local resource_type="$1"
    local resource_id="$2"
    local check_command="$3"

    if eval "$check_command" &>/dev/null; then
        echo "✅ $resource_type: $resource_id"
        return 0
    else
        echo "❌ $resource_type: $resource_id (존재하지 않음)"
        return 1
    fi
}

# ECS 리소스 확인
ECS_SERVICE_EXISTS=false
ECS_CLUSTER_EXISTS=false
ECR_REPO_EXISTS=false
ALB_EXISTS=false
TARGET_GROUP_EXISTS=false
SECURITY_GROUP_EXISTS=false
LOG_GROUP_EXISTS=false

echo "현재 존재하는 리소스:"

# ECS 서비스
if aws ecs describe-services --cluster "$ECS_CLUSTER_NAME" --services "$ECS_SERVICE_NAME" --region "$AWS_REGION" --query 'services[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
    echo "✅ ECS Service: $ECS_SERVICE_NAME"
    ECS_SERVICE_EXISTS=true
else
    echo "❌ ECS Service: $ECS_SERVICE_NAME (존재하지 않음)"
fi

# ECS 클러스터
if aws ecs describe-clusters --clusters "$ECS_CLUSTER_NAME" --region "$AWS_REGION" --query 'clusters[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
    echo "✅ ECS Cluster: $ECS_CLUSTER_NAME"
    ECS_CLUSTER_EXISTS=true
else
    echo "❌ ECS Cluster: $ECS_CLUSTER_NAME (존재하지 않음)"
fi

# ECR 리포지토리
if aws ecr describe-repositories --repository-names "$ECR_REPOSITORY_NAME" --region "$AWS_REGION" &>/dev/null; then
    echo "✅ ECR Repository: $ECR_REPOSITORY_NAME"
    ECR_REPO_EXISTS=true

    # ECR 이미지 개수 확인
    IMAGE_COUNT=$(aws ecr list-images --repository-name "$ECR_REPOSITORY_NAME" --region "$AWS_REGION" --query 'length(imageIds)' --output text 2>/dev/null || echo "0")
    echo "   📦 저장된 이미지: $IMAGE_COUNT개"
else
    echo "❌ ECR Repository: $ECR_REPOSITORY_NAME (존재하지 않음)"
fi

# ALB
if [ "$INFRA_INFO_EXISTS" = true ] && [ -n "$ALB_ARN" ]; then
    if aws elbv2 describe-load-balancers --load-balancer-arns "$ALB_ARN" --region "$AWS_REGION" &>/dev/null; then
        echo "✅ Application Load Balancer: $ALB_NAME"
        ALB_EXISTS=true
    else
        echo "❌ Application Load Balancer: $ALB_NAME (ARN으로 찾을 수 없음, 이름으로 재검색)"
        ALB_ARN=""
        ALB_EXISTS=false
    fi
else
    ALB_ARN=""
    ALB_EXISTS=false
fi

# ARN이 없거나 ARN으로 찾지 못한 경우 이름으로 검색
if [ "$ALB_EXISTS" = false ]; then
    ALB_RESULT=$(aws elbv2 describe-load-balancers --names "$ALB_NAME" --region "$AWS_REGION" --query 'LoadBalancers[0].LoadBalancerArn' --output text 2>/dev/null || echo "None")
    if [ "$ALB_RESULT" != "None" ] && [ -n "$ALB_RESULT" ] && [ "$ALB_RESULT" != "null" ]; then
        echo "✅ Application Load Balancer: $ALB_NAME"
        ALB_EXISTS=true
        ALB_ARN="$ALB_RESULT"
    else
        echo "❌ Application Load Balancer: $ALB_NAME (존재하지 않음)"
        ALB_EXISTS=false
        ALB_ARN=""
    fi
fi

# Target Group
if [ "$INFRA_INFO_EXISTS" = true ] && [ -n "$TARGET_GROUP_ARN" ]; then
    if aws elbv2 describe-target-groups --target-group-arns "$TARGET_GROUP_ARN" --region "$AWS_REGION" &>/dev/null; then
        echo "✅ Target Group: $TARGET_GROUP_NAME"
        TARGET_GROUP_EXISTS=true
    else
        echo "❌ Target Group: $TARGET_GROUP_NAME (ARN으로 찾을 수 없음, 이름으로 재검색)"
        TARGET_GROUP_ARN=""
        TARGET_GROUP_EXISTS=false
    fi
else
    TARGET_GROUP_ARN=""
    TARGET_GROUP_EXISTS=false
fi

# ARN이 없거나 ARN으로 찾지 못한 경우 이름으로 검색
if [ "$TARGET_GROUP_EXISTS" = false ]; then
    TG_RESULT=$(aws elbv2 describe-target-groups --names "$TARGET_GROUP_NAME" --region "$AWS_REGION" --query 'TargetGroups[0].TargetGroupArn' --output text 2>/dev/null || echo "None")
    if [ "$TG_RESULT" != "None" ] && [ -n "$TG_RESULT" ] && [ "$TG_RESULT" != "null" ]; then
        echo "✅ Target Group: $TARGET_GROUP_NAME"
        TARGET_GROUP_EXISTS=true
        TARGET_GROUP_ARN="$TG_RESULT"
    else
        echo "❌ Target Group: $TARGET_GROUP_NAME (존재하지 않음)"
        TARGET_GROUP_EXISTS=false
        TARGET_GROUP_ARN=""
    fi
fi

# 보안 그룹
if [ "$INFRA_INFO_EXISTS" = true ] && [ -n "$SECURITY_GROUP_ID" ]; then
    if aws ec2 describe-security-groups --group-ids "$SECURITY_GROUP_ID" --region "$AWS_REGION" &>/dev/null; then
        echo "✅ Security Group: $SECURITY_GROUP_NAME ($SECURITY_GROUP_ID)"
        SECURITY_GROUP_EXISTS=true
    else
        echo "❌ Security Group: $SECURITY_GROUP_NAME (존재하지 않음)"
    fi
else
    # ID가 없는 경우 이름으로 검색
    SG_RESULT=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$SECURITY_GROUP_NAME" --region "$AWS_REGION" --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")
    if [ "$SG_RESULT" != "None" ] && [ -n "$SG_RESULT" ]; then
        echo "✅ Security Group: $SECURITY_GROUP_NAME ($SG_RESULT)"
        SECURITY_GROUP_EXISTS=true
        SECURITY_GROUP_ID="$SG_RESULT"
    else
        echo "❌ Security Group: $SECURITY_GROUP_NAME (존재하지 않음)"
    fi
fi

# CloudWatch Logs
if aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP_NAME" --region "$AWS_REGION" --query "logGroups[?logGroupName=='$LOG_GROUP_NAME']" 2>/dev/null | grep -q "$LOG_GROUP_NAME"; then
    echo "✅ CloudWatch Log Group: $LOG_GROUP_NAME"
    LOG_GROUP_EXISTS=true
else
    echo "❌ CloudWatch Log Group: $LOG_GROUP_NAME (존재하지 않음)"
fi

echo ""

# 4. Dry Run 모드
if [ "$DRY_RUN" = true ]; then
    log_step "🧪 DRY RUN: 삭제 예정 리소스 (실제 삭제 안함)"
    echo ""

    if [ "$DELETE_SERVICE_ONLY" = true ]; then
        echo "🎯 서비스만 삭제 모드:"
        [ "$ECS_SERVICE_EXISTS" = true ] && echo "  - ECS Service: $ECS_SERVICE_NAME"
    else
        echo "🗑️  전체 삭제 모드:"
        [ "$ECS_SERVICE_EXISTS" = true ] && echo "  - ECS Service: $ECS_SERVICE_NAME"
        [ "$ECS_CLUSTER_EXISTS" = true ] && echo "  - ECS Cluster: $ECS_CLUSTER_NAME"
        [ "$ALB_EXISTS" = true ] && echo "  - Application Load Balancer: $ALB_NAME"
        [ "$TARGET_GROUP_EXISTS" = true ] && echo "  - Target Group: $TARGET_GROUP_NAME"
        [ "$SECURITY_GROUP_EXISTS" = true ] && echo "  - Security Group: $SECURITY_GROUP_NAME"
        [ "$ECR_REPO_EXISTS" = true ] && [ "$KEEP_ECR" = false ] && echo "  - ECR Repository: $ECR_REPOSITORY_NAME (이미지 포함)"
        [ "$LOG_GROUP_EXISTS" = true ] && [ "$KEEP_LOGS" = false ] && echo "  - CloudWatch Log Group: $LOG_GROUP_NAME"
        echo "  - IAM Roles: $TASK_EXECUTION_ROLE_NAME, $TASK_ROLE_NAME"
        echo "  - Task Definitions: $ECS_TASK_FAMILY (모든 리비전)"
    fi

    echo ""
    log_info "실제 삭제를 진행하려면 --dry-run 옵션을 제거하고 다시 실행하세요."
    exit 0
fi

# 5. 사용자 확인 (Force 모드가 아닌 경우)
if [ "$FORCE" = false ]; then
    echo ""
    if [ "$DELETE_SERVICE_ONLY" = true ]; then
        log_warning "ECS 서비스만 삭제합니다. 인프라 리소스는 유지됩니다."
    else
        log_warning "모든 AWS 리소스를 삭제합니다. 이 작업은 되돌릴 수 없습니다!"
        [ "$KEEP_ECR" = true ] && log_info "ECR 리포지토리는 유지됩니다."
        [ "$KEEP_LOGS" = true ] && log_info "CloudWatch 로그는 유지됩니다."
    fi

    echo ""
    read -p "계속 진행하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "삭제가 취소되었습니다."
        exit 0
    fi
fi

echo ""
log_step "🗑️  리소스 삭제 시작"

# 삭제 함수들
delete_resource() {
    local resource_name="$1"
    local delete_command="$2"
    local check_exists="$3"

    if [ "$check_exists" = true ]; then
        log_info "삭제 중: $resource_name"
        if eval "$delete_command" &>/dev/null; then
            log_success "$resource_name 삭제 완료"
        else
            log_warning "$resource_name 삭제 실패 또는 이미 삭제됨"
        fi
    else
        log_info "$resource_name: 존재하지 않음 (건너뜀)"
    fi
}

# 6. ECS 서비스 삭제
log_step "6. ECS 서비스 삭제"
if [ "$ECS_SERVICE_EXISTS" = true ]; then
    # 먼저 배포중인 태스크들을 강제 중지
    log_info "배포중인 태스크들 확인 및 강제 중지"
    RUNNING_TASKS=$(aws ecs list-tasks \
        --cluster "$ECS_CLUSTER_NAME" \
        --service-name "$ECS_SERVICE_NAME" \
        --region "$AWS_REGION" \
        --query 'taskArns[]' \
        --output text 2>/dev/null || echo "")

    if [ -n "$RUNNING_TASKS" ] && [ "$RUNNING_TASKS" != "None" ]; then
        log_info "실행중/배포중인 태스크 발견, 강제 중지 중..."
        for task_arn in $RUNNING_TASKS; do
            log_info "태스크 중지: $(basename $task_arn)"
            aws ecs stop-task \
                --cluster "$ECS_CLUSTER_NAME" \
                --task "$task_arn" \
                --region "$AWS_REGION" > /dev/null || true
        done

        # 태스크가 실제로 중지될 때까지 대기
        log_info "태스크 중지 완료 대기 중..."
        for i in {1..30}; do
            REMAINING_TASKS=$(aws ecs list-tasks \
                --cluster "$ECS_CLUSTER_NAME" \
                --service-name "$ECS_SERVICE_NAME" \
                --region "$AWS_REGION" \
                --query 'length(taskArns)' \
                --output text 2>/dev/null || echo "0")

            if [ "$REMAINING_TASKS" = "0" ]; then
                log_success "모든 태스크가 중지되었습니다"
                break
            fi

            log_info "남은 태스크: $REMAINING_TASKS 개 (${i}/30)"
            sleep 10
        done
    else
        log_info "실행중인 태스크가 없습니다"
    fi

    log_info "ECS 서비스 스케일링 다운 (desired count = 0)"
    aws ecs update-service \
        --cluster "$ECS_CLUSTER_NAME" \
        --service "$ECS_SERVICE_NAME" \
        --desired-count 0 \
        --region "$AWS_REGION" > /dev/null

    log_info "태스크가 모두 종료될 때까지 대기 중..."
    aws ecs wait services-stable \
        --cluster "$ECS_CLUSTER_NAME" \
        --services "$ECS_SERVICE_NAME" \
        --region "$AWS_REGION" \
        --cli-read-timeout 300 || log_warning "서비스 안정화 대기 시간 초과"

    log_info "ECS 서비스 삭제 중: $ECS_SERVICE_NAME"
    aws ecs delete-service \
        --cluster "$ECS_CLUSTER_NAME" \
        --service "$ECS_SERVICE_NAME" \
        --force \
        --region "$AWS_REGION" > /dev/null

    log_success "ECS 서비스 삭제 완료"
else
    log_info "ECS 서비스가 존재하지 않음 (건너뜀)"
fi

# 서비스만 삭제하는 경우 여기서 종료
if [ "$DELETE_SERVICE_ONLY" = true ]; then
    log_step "=== 서비스 삭제 완료 ==="
    log_success "ECS 서비스가 성공적으로 삭제되었습니다!"
    log_info "인프라 리소스는 유지되었습니다. 서비스를 재배포하려면 ./3-deploy-ecs-service.sh를 실행하세요."
    exit 0
fi

# 7. 클러스터 내 남은 태스크들 정리
log_step "7. 클러스터 내 남은 태스크들 정리"
if [ "$ECS_CLUSTER_EXISTS" = true ]; then
    log_info "클러스터 내 모든 태스크 조회 중..."
    ALL_TASKS=$(aws ecs list-tasks \
        --cluster "$ECS_CLUSTER_NAME" \
        --region "$AWS_REGION" \
        --query 'taskArns[]' \
        --output text 2>/dev/null || echo "")

    if [ -n "$ALL_TASKS" ] && [ "$ALL_TASKS" != "None" ]; then
        log_warning "클러스터에 남은 태스크 발견, 강제 중지 중..."
        for task_arn in $ALL_TASKS; do
            log_info "태스크 중지: $(basename $task_arn)"
            aws ecs stop-task \
                --cluster "$ECS_CLUSTER_NAME" \
                --task "$task_arn" \
                --reason "클러스터 정리를 위한 강제 중지" \
                --region "$AWS_REGION" > /dev/null || true
        done

        # 모든 태스크가 중지될 때까지 대기
        log_info "모든 태스크 중지 완료 대기 중..."
        for i in {1..60}; do
            REMAINING_TASKS=$(aws ecs list-tasks \
                --cluster "$ECS_CLUSTER_NAME" \
                --region "$AWS_REGION" \
                --query 'length(taskArns)' \
                --output text 2>/dev/null || echo "0")

            if [ "$REMAINING_TASKS" = "0" ]; then
                log_success "클러스터 내 모든 태스크가 정리되었습니다"
                break
            fi

            log_info "남은 태스크: $REMAINING_TASKS 개 (${i}/60)"
            sleep 5
        done

        if [ "$REMAINING_TASKS" != "0" ]; then
            log_warning "일부 태스크가 여전히 남아있지만 클러스터 삭제를 진행합니다"
        fi
    else
        log_info "클러스터에 남은 태스크가 없습니다"
    fi
else
    log_info "클러스터가 존재하지 않음 (태스크 정리 건너뜀)"
fi

# 8. ECS 클러스터 삭제
log_step "8. ECS 클러스터 삭제"
delete_resource "ECS Cluster ($ECS_CLUSTER_NAME)" \
    "aws ecs delete-cluster --cluster '$ECS_CLUSTER_NAME' --region '$AWS_REGION'" \
    "$ECS_CLUSTER_EXISTS"

# 9. Task Definition 등록 취소
log_step "9. Task Definition 정리"
log_info "Task Definition 리비전 조회 중: $ECS_TASK_FAMILY"

TASK_DEFINITIONS=$(aws ecs list-task-definitions \
    --family-prefix "$ECS_TASK_FAMILY" \
    --region "$AWS_REGION" \
    --query 'taskDefinitionArns' \
    --output text 2>/dev/null || echo "")

if [ -n "$TASK_DEFINITIONS" ]; then
    for task_def_arn in $TASK_DEFINITIONS; do
        log_info "Task Definition 등록 취소: $task_def_arn"
        aws ecs deregister-task-definition \
            --task-definition "$task_def_arn" \
            --region "$AWS_REGION" > /dev/null || true
    done
    log_success "모든 Task Definition 등록 취소 완료"
else
    log_info "등록된 Task Definition이 없음"
fi

# 10. ALB Listeners 삭제
log_step "10. ALB Listener 삭제"
if [ "$ALB_EXISTS" = true ] && [ -n "$ALB_ARN" ]; then
    LISTENERS=$(aws elbv2 describe-listeners \
        --load-balancer-arn "$ALB_ARN" \
        --region "$AWS_REGION" \
        --query 'Listeners[].ListenerArn' \
        --output text 2>/dev/null || echo "")

    if [ -n "$LISTENERS" ]; then
        for listener_arn in $LISTENERS; do
            log_info "Listener 삭제: $listener_arn"
            aws elbv2 delete-listener \
                --listener-arn "$listener_arn" \
                --region "$AWS_REGION" > /dev/null || true
        done
        log_success "모든 Listener 삭제 완료"
    else
        log_info "삭제할 Listener가 없음"
    fi
else
    log_info "ALB가 존재하지 않음 (Listener 삭제 건너뜀)"
fi

# 10. Application Load Balancer 삭제
log_step "10. Application Load Balancer 삭제"
if [ "$ALB_EXISTS" = true ] && [ -n "$ALB_ARN" ]; then
    log_info "ALB 삭제 중: $ALB_NAME"
    if aws elbv2 delete-load-balancer --load-balancer-arn "$ALB_ARN" --region "$AWS_REGION" &>/dev/null; then
        log_success "ALB 삭제 명령 전송 완료"

        # ALB 삭제 완료 대기 (최대 3분)
        log_info "ALB 삭제 완료 대기 중 (최대 180초)..."
        for i in {1..36}; do  # 36 × 5초 = 180초
            if ! aws elbv2 describe-load-balancers --load-balancer-arns "$ALB_ARN" --region "$AWS_REGION" &>/dev/null; then
                log_success "ALB 삭제 확인됨 (${i}회차, $((i*5))초 경과)"
                break
            fi
            if [ $i -eq 36 ]; then
                log_warning "ALB 삭제 대기 시간 초과, 계속 진행합니다"
            else
                sleep 5
            fi
        done
    else
        log_warning "ALB 삭제 실패 또는 이미 삭제됨"
    fi
else
    log_info "Application Load Balancer가 존재하지 않음 (건너뜀)"
fi

# 11. Target Group 삭제
log_step "11. Target Group 삭제"
if [ "$TARGET_GROUP_EXISTS" = true ] && [ -n "$TARGET_GROUP_ARN" ]; then
    log_info "Target Group 삭제 중: $TARGET_GROUP_NAME"
    # Target Group 삭제 재시도 (최대 3회)
    for attempt in {1..3}; do
        if aws elbv2 delete-target-group --target-group-arn "$TARGET_GROUP_ARN" --region "$AWS_REGION" &>/dev/null; then
            log_success "Target Group 삭제 완료 (시도 $attempt)"
            break
        else
            if [ $attempt -eq 3 ]; then
                log_warning "Target Group 삭제 실패 (3회 시도 후 포기)"
            else
                log_info "Target Group 삭제 실패, 재시도 중... (시도 $attempt/3)"
                sleep 10
            fi
        fi
    done
else
    log_info "Target Group이 존재하지 않음 (건너뜀)"
fi

# 12. 보안 그룹 삭제
log_step "12. 보안 그룹 삭제"
if [ "$SECURITY_GROUP_EXISTS" = true ] && [ -n "$SECURITY_GROUP_ID" ]; then
    log_info "보안 그룹 삭제 중: $SECURITY_GROUP_NAME ($SECURITY_GROUP_ID)"
    # 보안 그룹 삭제 재시도 (최대 3회)
    for attempt in {1..3}; do
        if aws ec2 delete-security-group --group-id "$SECURITY_GROUP_ID" --region "$AWS_REGION" &>/dev/null; then
            log_success "보안 그룹 삭제 완료 (시도 $attempt)"
            break
        else
            if [ $attempt -eq 3 ]; then
                log_warning "보안 그룹 삭제 실패 (3회 시도 후 포기) - 다른 리소스가 사용 중일 수 있음"
            else
                log_info "보안 그룹 삭제 실패, 재시도 중... (시도 $attempt/3)"
                sleep 10
            fi
        fi
    done
else
    log_info "보안 그룹이 존재하지 않음 (건너뜀)"
fi

# 13. ECR 이미지 및 리포지토리 삭제
if [ "$KEEP_ECR" = false ]; then
    log_step "13. ECR 리포지토리 삭제"
    if [ "$ECR_REPO_EXISTS" = true ]; then
        log_info "ECR 리포지토리 삭제 (모든 이미지 포함): $ECR_REPOSITORY_NAME"
        # ECR 삭제 재시도 (최대 3회)
        for attempt in {1..3}; do
            if aws ecr delete-repository \
                --repository-name "$ECR_REPOSITORY_NAME" \
                --force \
                --region "$AWS_REGION" &>/dev/null; then
                log_success "ECR 리포지토리 삭제 완료 (시도 $attempt)"
                break
            else
                if [ $attempt -eq 3 ]; then
                    log_warning "ECR 리포지토리 삭제 실패 (3회 시도 후 포기)"
                else
                    log_info "ECR 삭제 실패, 재시도 중... (시도 $attempt/3)"
                    sleep 5
                fi
            fi
        done
    else
        log_info "ECR 리포지토리가 존재하지 않음 (건너뜀)"
    fi
else
    log_step "13. ECR 리포지토리 유지"
    log_info "ECR 리포지토리를 유지합니다: $ECR_REPOSITORY_NAME"
fi

# 14. CloudWatch Logs 그룹 삭제
if [ "$KEEP_LOGS" = false ]; then
    log_step "14. CloudWatch Logs 그룹 삭제"
    if [ "$LOG_GROUP_EXISTS" = true ]; then
        log_info "CloudWatch Log Group 삭제 중: $LOG_GROUP_NAME"
        # CloudWatch Logs 삭제 재시도 (최대 3회)
        for attempt in {1..3}; do
            if aws logs delete-log-group --log-group-name "$LOG_GROUP_NAME" --region "$AWS_REGION" &>/dev/null; then
                log_success "CloudWatch Log Group 삭제 완료 (시도 $attempt)"
                break
            else
                if [ $attempt -eq 3 ]; then
                    log_warning "CloudWatch Log Group 삭제 실패 (3회 시도 후 포기)"
                else
                    log_info "CloudWatch Logs 삭제 실패, 재시도 중... (시도 $attempt/3)"
                    sleep 5
                fi
            fi
        done
    else
        log_info "CloudWatch Log Group이 존재하지 않음 (건너뜀)"
    fi
else
    log_step "14. CloudWatch Logs 그룹 유지"
    log_info "CloudWatch Logs 그룹을 유지합니다: $LOG_GROUP_NAME"
fi

# 15. IAM 역할 삭제
log_step "15. IAM 역할 삭제"

delete_iam_role() {
    local role_name="$1"
    local policy_arn="$2"

    if aws iam get-role --role-name "$role_name" &>/dev/null; then
        log_info "IAM 역할 삭제 중: $role_name"

        # 연결된 정책 제거 (재시도 포함)
        if [ -n "$policy_arn" ]; then
            for attempt in {1..3}; do
                if aws iam detach-role-policy \
                    --role-name "$role_name" \
                    --policy-arn "$policy_arn" &>/dev/null; then
                    log_info "정책 분리 완료: $policy_arn (시도 $attempt)"
                    break
                else
                    if [ $attempt -eq 3 ]; then
                        log_warning "정책 분리 실패, 계속 진행: $policy_arn"
                    else
                        sleep 2
                    fi
                fi
            done
        fi

        # 역할 삭제 (재시도 포함)
        for attempt in {1..3}; do
            if aws iam delete-role --role-name "$role_name" &>/dev/null; then
                log_success "IAM 역할 삭제 완료: $role_name (시도 $attempt)"
                return 0
            else
                if [ $attempt -eq 3 ]; then
                    log_warning "IAM 역할 삭제 실패 (3회 시도 후 포기): $role_name"
                else
                    log_info "IAM 역할 삭제 재시도... (시도 $attempt/3)"
                    sleep 5
                fi
            fi
        done
    else
        log_info "IAM 역할이 존재하지 않음: $role_name"
    fi
}

# Task Execution Role 삭제
delete_iam_role "$TASK_EXECUTION_ROLE_NAME" \
    "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"

# Task Role 삭제
delete_iam_role "$TASK_ROLE_NAME" ""

# 16. 임시 파일 정리
log_step "16. 임시 파일 정리"
rm -f "$SCRIPT_DIR/infrastructure.env" &>/dev/null || true
rm -f "$SCRIPT_DIR/ecs-task-definition-generated.json" &>/dev/null || true
log_info "임시 파일 정리 완료"

# 17. 삭제 상태 최종 확인
log_step "17. 삭제 상태 최종 확인"
log_info "모든 리소스 삭제 상태를 재확인합니다..."

FINAL_CHECK_FAILED=false

# ECS 클러스터 확인
if aws ecs describe-clusters --clusters "$ECS_CLUSTER_NAME" --region "$AWS_REGION" --query 'clusters[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
    log_warning "⚠️  ECS 클러스터가 여전히 활성 상태: $ECS_CLUSTER_NAME"
    FINAL_CHECK_FAILED=true
else
    log_success "✅ ECS 클러스터: 삭제됨"
fi

# ECR 리포지토리 확인 (KEEP_ECR이 false인 경우만)
if [ "$KEEP_ECR" = false ]; then
    if aws ecr describe-repositories --repository-names "$ECR_REPOSITORY_NAME" --region "$AWS_REGION" &>/dev/null; then
        log_warning "⚠️  ECR 리포지토리가 여전히 존재: $ECR_REPOSITORY_NAME"
        FINAL_CHECK_FAILED=true
    else
        log_success "✅ ECR 리포지토리: 삭제됨"
    fi
else
    log_info "📦 ECR 리포지토리: 유지됨 (의도적)"
fi

# ALB 확인
if aws elbv2 describe-load-balancers --names "$ALB_NAME" --region "$AWS_REGION" &>/dev/null; then
    log_warning "⚠️  ALB가 여전히 존재: $ALB_NAME"
    FINAL_CHECK_FAILED=true
else
    log_success "✅ Application Load Balancer: 삭제됨"
fi

# Target Group 확인
if aws elbv2 describe-target-groups --names "$TARGET_GROUP_NAME" --region "$AWS_REGION" &>/dev/null; then
    log_warning "⚠️  Target Group이 여전히 존재: $TARGET_GROUP_NAME"
    FINAL_CHECK_FAILED=true
else
    log_success "✅ Target Group: 삭제됨"
fi

# CloudWatch Logs 확인 (KEEP_LOGS이 false인 경우만)
if [ "$KEEP_LOGS" = false ]; then
    if aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP_NAME" --region "$AWS_REGION" --query "logGroups[?logGroupName=='$LOG_GROUP_NAME']" 2>/dev/null | grep -q "$LOG_GROUP_NAME"; then
        log_warning "⚠️  CloudWatch Log Group이 여전히 존재: $LOG_GROUP_NAME"
        FINAL_CHECK_FAILED=true
    else
        log_success "✅ CloudWatch Log Group: 삭제됨"
    fi
else
    log_info "📊 CloudWatch Log Group: 유지됨 (의도적)"
fi

# IAM 역할 확인
if aws iam get-role --role-name "$TASK_EXECUTION_ROLE_NAME" &>/dev/null; then
    log_warning "⚠️  IAM 역할이 여전히 존재: $TASK_EXECUTION_ROLE_NAME"
    FINAL_CHECK_FAILED=true
else
    log_success "✅ Task Execution Role: 삭제됨"
fi

if aws iam get-role --role-name "$TASK_ROLE_NAME" &>/dev/null; then
    log_warning "⚠️  IAM 역할이 여전히 존재: $TASK_ROLE_NAME"
    FINAL_CHECK_FAILED=true
else
    log_success "✅ Task Role: 삭제됨"
fi

if [ "$FINAL_CHECK_FAILED" = true ]; then
    log_warning "일부 리소스가 완전히 삭제되지 않았습니다. 수동 확인이 필요할 수 있습니다."
else
    log_success "모든 리소스 삭제 확인 완료!"
fi

# 18. 완료 메시지
log_step "=== 리소스 정리 완료 ==="
echo ""
if [ "$FINAL_CHECK_FAILED" = true ]; then
    log_warning "리소스 정리가 완료되었지만 일부 항목이 완전히 삭제되지 않았을 수 있습니다."
    echo "수동 확인 후 필요시 AWS 콘솔에서 직접 삭제하세요."
else
    log_success "모든 AWS 리소스가 성공적으로 정리되었습니다!"
fi
echo ""
echo "🗑️  삭제된 리소스:"
echo "   ✅ ECS Service: $ECS_SERVICE_NAME"
echo "   ✅ ECS Cluster: $ECS_CLUSTER_NAME"
echo "   ✅ Task Definitions: $ECS_TASK_FAMILY (모든 리비전)"
echo "   ✅ Application Load Balancer: $ALB_NAME"
echo "   ✅ Target Group: $TARGET_GROUP_NAME"
echo "   ✅ Security Group: $SECURITY_GROUP_NAME"
echo "   ✅ IAM Roles: $TASK_EXECUTION_ROLE_NAME, $TASK_ROLE_NAME"

if [ "$KEEP_ECR" = false ]; then
    echo "   ✅ ECR Repository: $ECR_REPOSITORY_NAME"
else
    echo "   🔒 ECR Repository: $ECR_REPOSITORY_NAME (유지됨)"
fi

if [ "$KEEP_LOGS" = false ]; then
    echo "   ✅ CloudWatch Log Group: $LOG_GROUP_NAME"
else
    echo "   🔒 CloudWatch Log Group: $LOG_GROUP_NAME (유지됨)"
fi

echo ""
echo "💰 비용 절약: 더 이상 AWS 요금이 발생하지 않습니다."
echo ""

if [ "$KEEP_ECR" = true ] || [ "$KEEP_LOGS" = true ]; then
    echo "ℹ️  유지된 리소스가 있습니다:"
    [ "$KEEP_ECR" = true ] && echo "   - ECR 이미지는 계속 저장 요금이 발생할 수 있습니다"
    [ "$KEEP_LOGS" = true ] && echo "   - CloudWatch 로그는 계속 저장 요금이 발생할 수 있습니다"
    echo ""
fi

log_success "리소스 정리 스크립트 실행 완료!"