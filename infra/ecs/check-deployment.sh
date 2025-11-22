#!/bin/bash

# 배포 상태 확인 스크립트
# ECS 서비스, ALB, Target Group 헬스 상태를 종합적으로 확인합니다.

set -e

# 스크립트 위치 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 설정 파일 로드
source "$SCRIPT_DIR/config.sh"

log_step "=== 배포 상태 확인 시작 ==="
echo ""

# 1. 환경 설정 확인
log_step "1. 환경 설정 확인"
load_env
check_aws_cli

# 2. 인프라 정보 로드
log_step "2. 인프라 정보 로드"
if [ ! -f "$SCRIPT_DIR/infrastructure.env" ]; then
    log_error "인프라 정보 파일을 찾을 수 없습니다: $SCRIPT_DIR/infrastructure.env"
    exit 1
fi

source "$SCRIPT_DIR/infrastructure.env"
log_success "인프라 정보 로드 완료"
echo ""

# 3. ECS 클러스터 상태 확인
log_step "3. ECS 클러스터 상태 확인"
CLUSTER_STATUS=$(aws ecs describe-clusters \
    --clusters "$ECS_CLUSTER_NAME" \
    --region "$AWS_REGION" \
    --query 'clusters[0].status' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$CLUSTER_STATUS" = "ACTIVE" ]; then
    log_success "클러스터 상태: ACTIVE"
else
    log_error "클러스터 상태: $CLUSTER_STATUS"
    exit 1
fi

# 4. ECS 서비스 상태 확인
log_step "4. ECS 서비스 상태 확인"
SERVICE_INFO=$(aws ecs describe-services \
    --cluster "$ECS_CLUSTER_NAME" \
    --services "$ECS_SERVICE_NAME" \
    --region "$AWS_REGION" \
    --query 'services[0].[status,runningCount,desiredCount]' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$SERVICE_INFO" = "NOT_FOUND" ]; then
    log_error "서비스를 찾을 수 없습니다: $ECS_SERVICE_NAME"
    exit 1
fi

SERVICE_STATUS=$(echo "$SERVICE_INFO" | awk '{print $1}')
RUNNING_COUNT=$(echo "$SERVICE_INFO" | awk '{print $2}')
DESIRED_COUNT=$(echo "$SERVICE_INFO" | awk '{print $3}')

if [ "$SERVICE_STATUS" = "ACTIVE" ]; then
    log_success "서비스 상태: ACTIVE"
    log_info "실행 중인 태스크: $RUNNING_COUNT/$DESIRED_COUNT"

    if [ "$RUNNING_COUNT" -eq "$DESIRED_COUNT" ]; then
        log_success "모든 태스크가 정상 실행 중입니다"
    else
        log_warning "일부 태스크가 실행 중이지 않습니다"
    fi
else
    log_error "서비스 상태: $SERVICE_STATUS"
    exit 1
fi
echo ""

# 5. Target Group 헬스체크 상태 확인
log_step "5. Target Group 헬스체크 상태 확인"
TARGET_HEALTH=$(aws elbv2 describe-target-health \
    --target-group-arn "$TARGET_GROUP_ARN" \
    --region "$AWS_REGION" \
    --query 'TargetHealthDescriptions[*].[Target.Id,TargetHealth.State,TargetHealth.Reason]' \
    --output text 2>/dev/null || echo "ERROR")

if [ "$TARGET_HEALTH" = "ERROR" ]; then
    log_error "Target Group 정보를 가져올 수 없습니다"
    exit 1
fi

HEALTHY_COUNT=$(echo "$TARGET_HEALTH" | grep -c "healthy" || echo "0")
TOTAL_COUNT=$(echo "$TARGET_HEALTH" | wc -l)

if [ "$HEALTHY_COUNT" -gt 0 ]; then
    log_success "헬시한 타겟: $HEALTHY_COUNT/$TOTAL_COUNT"
    echo "$TARGET_HEALTH" | while read -r target_id state reason; do
        if [ "$state" = "healthy" ]; then
            log_info "  ✓ $target_id: $state"
        else
            log_warning "  ✗ $target_id: $state ($reason)"
        fi
    done
else
    log_error "헬시한 타겟이 없습니다"
    echo "$TARGET_HEALTH"
    exit 1
fi
echo ""

# 6. ALB 상태 확인
log_step "6. Application Load Balancer 상태 확인"
ALB_STATE=$(aws elbv2 describe-load-balancers \
    --load-balancer-arns "$ALB_ARN" \
    --region "$AWS_REGION" \
    --query 'LoadBalancers[0].State.Code' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$ALB_STATE" = "active" ]; then
    log_success "ALB 상태: active"
    log_info "ALB DNS: $ALB_DNS"
else
    log_error "ALB 상태: $ALB_STATE"
    exit 1
fi
echo ""

# 7. 실제 HTTP 요청 테스트
log_step "7. HTTP 요청 테스트"
log_info "애플리케이션 URL로 요청을 보냅니다..."

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "http://$ALB_DNS" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
    log_success "HTTP 응답 코드: $HTTP_CODE (정상)"
elif [ "$HTTP_CODE" = "000" ]; then
    log_error "HTTP 요청 실패: 연결할 수 없습니다"
else
    log_warning "HTTP 응답 코드: $HTTP_CODE"
fi
echo ""

# 8. CloudWatch 로그 최근 에러 확인
log_step "8. CloudWatch 로그 확인 (최근 5분)"
log_info "최근 에러 로그를 확인합니다..."

ERROR_COUNT=$(aws logs filter-log-events \
    --log-group-name "$LOG_GROUP_NAME" \
    --region "$AWS_REGION" \
    --start-time $(($(date +%s) * 1000 - 300000)) \
    --filter-pattern "ERROR" \
    --query 'length(events)' \
    --output text 2>/dev/null || echo "0")

if [ "$ERROR_COUNT" = "0" ]; then
    log_success "최근 5분간 에러 로그 없음"
else
    log_warning "최근 5분간 에러 로그: $ERROR_COUNT건"
    log_info "자세한 로그 확인: aws logs tail $LOG_GROUP_NAME --region $AWS_REGION --since 5m --filter-pattern ERROR"
fi
echo ""

# 9. 최근 서비스 이벤트 확인
log_step "9. 최근 서비스 이벤트 (최근 3개)"
aws ecs describe-services \
    --cluster "$ECS_CLUSTER_NAME" \
    --services "$ECS_SERVICE_NAME" \
    --region "$AWS_REGION" \
    --query 'services[0].events[:3].[createdAt,message]' \
    --output table 2>/dev/null || log_warning "서비스 이벤트를 가져올 수 없습니다"
echo ""

# 10. 최종 결과 요약
log_step "=== 배포 상태 확인 완료 ==="
echo ""

# 전체 상태 판단
ALL_CHECKS_PASSED=true

if [ "$CLUSTER_STATUS" != "ACTIVE" ]; then ALL_CHECKS_PASSED=false; fi
if [ "$SERVICE_STATUS" != "ACTIVE" ]; then ALL_CHECKS_PASSED=false; fi
if [ "$RUNNING_COUNT" -ne "$DESIRED_COUNT" ]; then ALL_CHECKS_PASSED=false; fi
if [ "$HEALTHY_COUNT" -eq 0 ]; then ALL_CHECKS_PASSED=false; fi
if [ "$ALB_STATE" != "active" ]; then ALL_CHECKS_PASSED=false; fi
if [ "$HTTP_CODE" != "200" ]; then ALL_CHECKS_PASSED=false; fi

if [ "$ALL_CHECKS_PASSED" = true ]; then
    log_success "✅ 모든 상태 확인 통과!"
    echo ""
    echo "📊 상태 요약:"
    echo "  🏗️  ECS 클러스터: $ECS_CLUSTER_NAME (ACTIVE)"
    echo "  🚀 ECS 서비스: $ECS_SERVICE_NAME (ACTIVE, $RUNNING_COUNT/$DESIRED_COUNT)"
    echo "  ❤️  헬시한 타겟: $HEALTHY_COUNT/$TOTAL_COUNT"
    echo "  ⚖️  ALB 상태: active"
    echo "  🌐 HTTP 응답: $HTTP_CODE"
    echo ""
    echo "🔗 애플리케이션 URL: http://$ALB_DNS"
    echo ""
    exit 0
else
    log_error "⚠️  일부 상태 확인 실패"
    echo ""
    echo "문제 해결을 위해 다음 명령어를 실행하세요:"
    echo ""
    echo "# ECS 서비스 상세 정보"
    echo "aws ecs describe-services --cluster $ECS_CLUSTER_NAME --services $ECS_SERVICE_NAME --region $AWS_REGION"
    echo ""
    echo "# CloudWatch 로그 실시간 확인"
    echo "aws logs tail $LOG_GROUP_NAME --follow --region $AWS_REGION"
    echo ""
    echo "# Target Group 헬스 상태"
    echo "aws elbv2 describe-target-health --target-group-arn $TARGET_GROUP_ARN --region $AWS_REGION"
    echo ""
    exit 1
fi
