#!/bin/bash

# ECS 서비스 배포 스크립트
# 이 스크립트는 ECS 클러스터, Task Definition, 서비스를 생성하고 배포합니다.

set -e  # 에러 발생 시 스크립트 중단

# 스크립트 위치 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 설정 파일 로드
source "$SCRIPT_DIR/config.sh"

log_step "=== ECS 서비스 배포 시작 ==="

# 1. 환경 설정 확인
log_step "1. 환경 설정 확인"
load_env
check_aws_cli

# 2. 인프라 정보 로드
log_step "2. 인프라 정보 로드"
if [ ! -f "$SCRIPT_DIR/infrastructure.env" ]; then
    log_error "인프라 정보 파일을 찾을 수 없습니다: $SCRIPT_DIR/infrastructure.env"
    log_error "먼저 ./2-setup-infrastructure.sh 를 실행하세요."
    exit 1
fi

source "$SCRIPT_DIR/infrastructure.env"
log_success "인프라 정보 로드 완료"

# 3. ECS 클러스터 생성
log_step "3. ECS 클러스터 생성"
if check_ecs_cluster; then
    log_info "ECS 클러스터가 이미 존재: $ECS_CLUSTER_NAME"
else
    aws ecs create-cluster \
        --cluster-name "$ECS_CLUSTER_NAME" \
        --region "$AWS_REGION" > /dev/null

    log_success "ECS 클러스터 생성: $ECS_CLUSTER_NAME"
fi

# 4. Task Definition JSON 파일 업데이트
log_step "4. Task Definition 업데이트"

# 동적 Task Definition 생성
cat > "$SCRIPT_DIR/ecs-task-definition-generated.json" << EOF
{
    "family": "$ECS_TASK_FAMILY",
    "networkMode": "awsvpc",
    "requiresCompatibilities": ["FARGATE"],
    "cpu": "$ECS_CPU",
    "memory": "$ECS_MEMORY",
    "executionRoleArn": "$TASK_EXECUTION_ROLE_ARN",
    "taskRoleArn": "$TASK_ROLE_ARN",
    "containerDefinitions": [
        {
            "name": "$ECS_CONTAINER_NAME",
            "image": "$ECR_IMAGE_URI:latest",
            "portMappings": [
                {
                    "containerPort": $CONTAINER_PORT,
                    "protocol": "tcp"
                }
            ],
            "essential": true,
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": "$LOG_GROUP_NAME",
                    "awslogs-region": "$AWS_REGION",
                    "awslogs-stream-prefix": "ecs"
                }
            },
            "environment": []
        }
    ]
}
EOF

log_success "Task Definition 생성: $SCRIPT_DIR/ecs-task-definition-generated.json"

# 5. Task Definition 등록
log_step "5. Task Definition 등록"
TASK_DEFINITION_ARN=$(aws ecs register-task-definition \
    --cli-input-json file://"$SCRIPT_DIR/ecs-task-definition-generated.json" \
    --region "$AWS_REGION" \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text)

TASK_REVISION=$(echo "$TASK_DEFINITION_ARN" | rev | cut -d':' -f1 | rev)
log_success "Task Definition 등록: $ECS_TASK_FAMILY:$TASK_REVISION"

# 6. ECS 서비스 생성 또는 업데이트
log_step "6. ECS 서비스 배포"

# 서브넷 배열 변환
SUBNET_ARRAY=($SUBNET_IDS)

if check_ecs_service; then
    log_info "기존 ECS 서비스 업데이트: $ECS_SERVICE_NAME"

    # 서비스 업데이트
    aws ecs update-service \
        --cluster "$ECS_CLUSTER_NAME" \
        --service "$ECS_SERVICE_NAME" \
        --task-definition "$ECS_TASK_FAMILY:$TASK_REVISION" \
        --desired-count "$ECS_DESIRED_COUNT" \
        --region "$AWS_REGION" > /dev/null

    log_success "ECS 서비스 업데이트 시작"
else
    log_info "새 ECS 서비스 생성: $ECS_SERVICE_NAME"

    # 새 서비스 생성
    aws ecs create-service \
        --cluster "$ECS_CLUSTER_NAME" \
        --service-name "$ECS_SERVICE_NAME" \
        --task-definition "$ECS_TASK_FAMILY:$TASK_REVISION" \
        --desired-count "$ECS_DESIRED_COUNT" \
        --launch-type FARGATE \
        --network-configuration "awsvpcConfiguration={subnets=[${SUBNET_ARRAY[0]},${SUBNET_ARRAY[1]}],securityGroups=[$SECURITY_GROUP_ID],assignPublicIp=ENABLED}" \
        --load-balancers "targetGroupArn=$TARGET_GROUP_ARN,containerName=$ECS_CONTAINER_NAME,containerPort=$CONTAINER_PORT" \
        --health-check-grace-period-seconds 300 \
        --region "$AWS_REGION" > /dev/null

    log_success "ECS 서비스 생성 완료"
fi

# 7. 배포 상태 확인
log_step "7. 배포 상태 확인"
log_info "서비스 안정화를 기다리는 중... (최대 10분)"

# 서비스 안정화 대기
if aws ecs wait services-stable \
    --cluster "$ECS_CLUSTER_NAME" \
    --services "$ECS_SERVICE_NAME" \
    --region "$AWS_REGION" \
    --cli-read-timeout 600 \
    --cli-connect-timeout 60; then

    log_success "서비스가 안정화되었습니다!"
else
    log_warning "서비스 안정화 대기 시간이 초과되었습니다. 수동으로 상태를 확인하세요."
fi

# 8. 서비스 상태 확인
log_step "8. 서비스 상태 확인"

# 실행 중인 태스크 수 확인
RUNNING_TASKS=$(aws ecs describe-services \
    --cluster "$ECS_CLUSTER_NAME" \
    --services "$ECS_SERVICE_NAME" \
    --region "$AWS_REGION" \
    --query 'services[0].runningCount' \
    --output text)

DESIRED_TASKS=$(aws ecs describe-services \
    --cluster "$ECS_CLUSTER_NAME" \
    --services "$ECS_SERVICE_NAME" \
    --region "$AWS_REGION" \
    --query 'services[0].desiredCount' \
    --output text)

log_info "실행 중인 태스크: $RUNNING_TASKS/$DESIRED_TASKS"

# Target Group 헬스체크 상태 확인
log_info "Target Group 헬스체크 상태 확인 중..."
sleep 30  # 헬스체크가 시작될 시간을 줌

HEALTHY_TARGETS=$(aws elbv2 describe-target-health \
    --target-group-arn "$TARGET_GROUP_ARN" \
    --region "$AWS_REGION" \
    --query 'length(TargetHealthDescriptions[?TargetHealth.State==`healthy`])' \
    --output text 2>/dev/null || echo "0")

log_info "헬시한 타겟 수: $HEALTHY_TARGETS"

# 9. 로그 확인 (최근 10개 이벤트)
log_step "9. 최근 서비스 이벤트 확인"
aws ecs describe-services \
    --cluster "$ECS_CLUSTER_NAME" \
    --services "$ECS_SERVICE_NAME" \
    --region "$AWS_REGION" \
    --query 'services[0].events[:5].[createdAt,message]' \
    --output table

# 10. 정리 작업
log_step "10. 임시 파일 정리"
rm -f "$SCRIPT_DIR/ecs-task-definition-generated.json"

# 11. 결과 출력
log_step "=== ECS 서비스 배포 완료 ==="
echo ""
log_success "ECS 서비스가 성공적으로 배포되었습니다!"
echo ""
echo "📋 서비스 정보:"
echo "🏗️  클러스터: $ECS_CLUSTER_NAME"
echo "🚀 서비스: $ECS_SERVICE_NAME"
echo "📋 Task Definition: $ECS_TASK_FAMILY:$TASK_REVISION"
echo "⚡ 실행 중인 태스크: $RUNNING_TASKS/$DESIRED_TASKS"
echo "❤️  헬시한 타겟: $HEALTHY_TARGETS"
echo ""
echo "🌐 애플리케이션 URL: http://$ALB_DNS"
echo ""
echo "🔗 ECS Console: https://$AWS_REGION.console.aws.amazon.com/ecs/home?region=$AWS_REGION#/clusters/$ECS_CLUSTER_NAME/services"
echo "📊 CloudWatch Logs: https://$AWS_REGION.console.aws.amazon.com/cloudwatch/home?region=$AWS_REGION#logsV2:log-groups/log-group/$(echo "$LOG_GROUP_NAME" | sed 's|/|%2F|g')"
echo ""

# 12. 배포 후 확인 사항 안내
if [ "$HEALTHY_TARGETS" = "0" ]; then
    log_warning "아직 헬시한 타겟이 없습니다. 다음을 확인하세요:"
    echo "  1. 애플리케이션이 포트 $CONTAINER_PORT 에서 정상적으로 실행되는지 확인"
    echo "  2. 헬스체크 경로 '/' 가 200 응답을 반환하는지 확인"
    echo "  3. CloudWatch 로그에서 애플리케이션 오류가 있는지 확인"
    echo "  4. 5-10분 후 다시 상태를 확인하세요"
else
    log_success "배포가 성공적으로 완료되었습니다!"
    echo "  ✅ 애플리케이션이 정상적으로 실행 중입니다"
    echo "  🔗 브라우저에서 http://$ALB_DNS 로 접속하세요"
fi

# 헬프 명령어 제공
echo ""
echo "🛠️  유용한 명령어:"
echo "  # 서비스 상태 확인"
echo "  aws ecs describe-services --cluster $ECS_CLUSTER_NAME --services $ECS_SERVICE_NAME --region $AWS_REGION"
echo ""
echo "  # 실행 중인 태스크 목록"
echo "  aws ecs list-tasks --cluster $ECS_CLUSTER_NAME --service-name $ECS_SERVICE_NAME --region $AWS_REGION"
echo ""
echo "  # CloudWatch 로그 실시간 확인"
echo "  aws logs tail $LOG_GROUP_NAME --follow --region $AWS_REGION"

log_success "배포 스크립트 실행 완료!"