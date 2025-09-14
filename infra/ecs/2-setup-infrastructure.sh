#!/bin/bash

# AWS 네트워크 인프라 구성 스크립트
# 이 스크립트는 ECS 서비스에 필요한 AWS 인프라를 설정합니다.

set -e  # 에러 발생 시 스크립트 중단

# 스크립트 위치 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 설정 파일 로드
source "$SCRIPT_DIR/config.sh"

log_step "=== AWS 네트워크 인프라 구성 시작 ==="

# 1. 환경 설정 확인
log_step "1. 환경 설정 확인"
load_env
check_aws_cli

# 2. 기본 VPC 및 서브넷 확인
log_step "2. VPC 및 서브넷 확인"
VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=isDefault,Values=true" \
    --query 'Vpcs[0].VpcId' \
    --output text --region "$AWS_REGION")

if [ "$VPC_ID" = "None" ] || [ -z "$VPC_ID" ]; then
    log_error "기본 VPC를 찾을 수 없습니다."
    exit 1
fi

log_success "기본 VPC 찾음: $VPC_ID"

# 서브넷 조회 (최소 2개 필요)
SUBNET_IDS=$(aws ec2 describe-subnets \
    --filters "Name=vpc-id,Values=$VPC_ID" "Name=default-for-az,Values=true" \
    --query 'Subnets[*].SubnetId' \
    --output text --region "$AWS_REGION")

SUBNET_ARRAY=($SUBNET_IDS)
if [ ${#SUBNET_ARRAY[@]} -lt 2 ]; then
    log_error "최소 2개의 서브넷이 필요합니다. 현재: ${#SUBNET_ARRAY[@]}개"
    exit 1
fi

log_success "서브넷 찾음: ${#SUBNET_ARRAY[@]}개"
for subnet in "${SUBNET_ARRAY[@]}"; do
    log_info "- $subnet"
done

# 3. 보안 그룹 생성
log_step "3. 보안 그룹 생성"
SECURITY_GROUP_ID=""

# 기존 보안 그룹 확인
EXISTING_SG=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=$SECURITY_GROUP_NAME" "Name=vpc-id,Values=$VPC_ID" \
    --query 'SecurityGroups[0].GroupId' \
    --output text --region "$AWS_REGION" 2>/dev/null || echo "None")

if [ "$EXISTING_SG" != "None" ] && [ -n "$EXISTING_SG" ]; then
    SECURITY_GROUP_ID="$EXISTING_SG"
    log_info "기존 보안 그룹 사용: $SECURITY_GROUP_ID"
else
    # 새 보안 그룹 생성
    SECURITY_GROUP_ID=$(aws ec2 create-security-group \
        --group-name "$SECURITY_GROUP_NAME" \
        --description "Security group for $PROJECT_NAME $APP_NAME ECS service" \
        --vpc-id "$VPC_ID" \
        --query 'GroupId' \
        --output text --region "$AWS_REGION")

    log_success "보안 그룹 생성: $SECURITY_GROUP_ID"

    # 인바운드 규칙 추가
    aws ec2 authorize-security-group-ingress \
        --group-id "$SECURITY_GROUP_ID" \
        --protocol tcp \
        --port 80 \
        --cidr "0.0.0.0/0" \
        --region "$AWS_REGION" > /dev/null

    aws ec2 authorize-security-group-ingress \
        --group-id "$SECURITY_GROUP_ID" \
        --protocol tcp \
        --port "$CONTAINER_PORT" \
        --cidr "0.0.0.0/0" \
        --region "$AWS_REGION" > /dev/null

    log_success "보안 그룹 인바운드 규칙 추가 완료"
fi

# 4. IAM 역할 생성
log_step "4. IAM 역할 생성"

# Task Execution Role 생성
create_iam_role() {
    local role_name="$1"
    local policy_arn="$2"
    local description="$3"

    if aws iam get-role --role-name "$role_name" --region "$AWS_REGION" &> /dev/null; then
        log_info "IAM 역할이 이미 존재: $role_name"
    else
        # Trust Policy 문서 생성
        cat > /tmp/trust-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "ecs-tasks.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
EOF

        aws iam create-role \
            --role-name "$role_name" \
            --assume-role-policy-document file:///tmp/trust-policy.json \
            --description "$description" \
            --region "$AWS_REGION" > /dev/null

        if [ -n "$policy_arn" ]; then
            aws iam attach-role-policy \
                --role-name "$role_name" \
                --policy-arn "$policy_arn" \
                --region "$AWS_REGION" > /dev/null
        fi

        log_success "IAM 역할 생성: $role_name"
        rm -f /tmp/trust-policy.json
    fi
}

# Task Execution Role (ECR 접근 권한)
create_iam_role "$TASK_EXECUTION_ROLE_NAME" \
    "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy" \
    "ECS Task Execution Role for $PROJECT_NAME"

# Task Role (애플리케이션이 AWS 서비스에 접근할 때 사용)
create_iam_role "$TASK_ROLE_NAME" \
    "" \
    "ECS Task Role for $PROJECT_NAME"

# 5. CloudWatch Logs 그룹 생성
log_step "5. CloudWatch Logs 그룹 생성"
if aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP_NAME" --region "$AWS_REGION" \
    --query "logGroups[?logGroupName=='$LOG_GROUP_NAME']" | grep -q "$LOG_GROUP_NAME"; then
    log_info "CloudWatch Logs 그룹이 이미 존재: $LOG_GROUP_NAME"
else
    aws logs create-log-group \
        --log-group-name "$LOG_GROUP_NAME" \
        --region "$AWS_REGION" > /dev/null

    aws logs put-retention-policy \
        --log-group-name "$LOG_GROUP_NAME" \
        --retention-in-days "$LOG_RETENTION_DAYS" \
        --region "$AWS_REGION" > /dev/null

    log_success "CloudWatch Logs 그룹 생성: $LOG_GROUP_NAME (보존 기간: ${LOG_RETENTION_DAYS}일)"
fi

# 6. Application Load Balancer 생성
log_step "6. Application Load Balancer 생성"

# 기존 ALB 확인
EXISTING_ALB=$(aws elbv2 describe-load-balancers \
    --names "$ALB_NAME" \
    --query 'LoadBalancers[0].LoadBalancerArn' \
    --output text --region "$AWS_REGION" 2>/dev/null || echo "None")

if [ "$EXISTING_ALB" != "None" ] && [ -n "$EXISTING_ALB" ]; then
    ALB_ARN="$EXISTING_ALB"
    ALB_DNS=$(aws elbv2 describe-load-balancers \
        --load-balancer-arns "$ALB_ARN" \
        --query 'LoadBalancers[0].DNSName' \
        --output text --region "$AWS_REGION")
    log_info "기존 ALB 사용: $ALB_DNS"
else
    # 새 ALB 생성 (최소 2개 서브넷 사용)
    ALB_ARN=$(aws elbv2 create-load-balancer \
        --name "$ALB_NAME" \
        --subnets "${SUBNET_ARRAY[0]}" "${SUBNET_ARRAY[1]}" \
        --security-groups "$SECURITY_GROUP_ID" \
        --scheme internet-facing \
        --type application \
        --ip-address-type ipv4 \
        --query 'LoadBalancers[0].LoadBalancerArn' \
        --output text --region "$AWS_REGION")

    ALB_DNS=$(aws elbv2 describe-load-balancers \
        --load-balancer-arns "$ALB_ARN" \
        --query 'LoadBalancers[0].DNSName' \
        --output text --region "$AWS_REGION")

    log_success "ALB 생성: $ALB_DNS"
fi

# 7. Target Group 생성
log_step "7. Target Group 생성"

# 기존 Target Group 확인
EXISTING_TG=$(aws elbv2 describe-target-groups \
    --names "$TARGET_GROUP_NAME" \
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text --region "$AWS_REGION" 2>/dev/null || echo "None")

if [ "$EXISTING_TG" != "None" ] && [ -n "$EXISTING_TG" ]; then
    TARGET_GROUP_ARN="$EXISTING_TG"
    log_info "기존 Target Group 사용: $TARGET_GROUP_ARN"
else
    TARGET_GROUP_ARN=$(aws elbv2 create-target-group \
        --name "$TARGET_GROUP_NAME" \
        --protocol HTTP \
        --port "$CONTAINER_PORT" \
        --vpc-id "$VPC_ID" \
        --target-type ip \
        --health-check-path "/" \
        --health-check-protocol HTTP \
        --health-check-interval-seconds 30 \
        --healthy-threshold-count 2 \
        --unhealthy-threshold-count 5 \
        --query 'TargetGroups[0].TargetGroupArn' \
        --output text --region "$AWS_REGION")

    log_success "Target Group 생성: $TARGET_GROUP_ARN"
fi

# 8. Listener 생성 또는 확인
log_step "8. ALB Listener 생성"

# 기존 Listener 확인
EXISTING_LISTENER=$(aws elbv2 describe-listeners \
    --load-balancer-arn "$ALB_ARN" \
    --query "Listeners[?Port==\`$ALB_PORT\`].ListenerArn" \
    --output text --region "$AWS_REGION" 2>/dev/null || echo "")

if [ -n "$EXISTING_LISTENER" ] && [ "$EXISTING_LISTENER" != "None" ]; then
    # 기존 Listener의 Default Action 업데이트
    aws elbv2 modify-listener \
        --listener-arn "$EXISTING_LISTENER" \
        --default-actions Type=forward,TargetGroupArn="$TARGET_GROUP_ARN" \
        --region "$AWS_REGION" > /dev/null

    log_info "기존 Listener 업데이트: $EXISTING_LISTENER"
else
    LISTENER_ARN=$(aws elbv2 create-listener \
        --load-balancer-arn "$ALB_ARN" \
        --protocol HTTP \
        --port "$ALB_PORT" \
        --default-actions Type=forward,TargetGroupArn="$TARGET_GROUP_ARN" \
        --query 'Listeners[0].ListenerArn' \
        --output text --region "$AWS_REGION")

    log_success "Listener 생성: $LISTENER_ARN"
fi

# 9. 인프라 정보 저장 (다음 스크립트에서 사용)
log_step "9. 인프라 정보 저장"
cat > "$SCRIPT_DIR/infrastructure.env" << EOF
# 자동 생성된 인프라 정보 - 수동으로 수정하지 마세요
VPC_ID="$VPC_ID"
SUBNET_IDS="${SUBNET_ARRAY[0]} ${SUBNET_ARRAY[1]}"
SECURITY_GROUP_ID="$SECURITY_GROUP_ID"
ALB_ARN="$ALB_ARN"
ALB_DNS="$ALB_DNS"
TARGET_GROUP_ARN="$TARGET_GROUP_ARN"
TASK_EXECUTION_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${TASK_EXECUTION_ROLE_NAME}"
TASK_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${TASK_ROLE_NAME}"
EOF

log_success "인프라 정보 저장: $SCRIPT_DIR/infrastructure.env"

# 10. 결과 출력
log_step "=== 네트워크 인프라 구성 완료 ==="
echo ""
log_success "AWS 인프라가 성공적으로 구성되었습니다!"
echo ""
echo "📋 생성된 리소스:"
echo "🌐 VPC ID: $VPC_ID"
echo "🔒 Security Group: $SECURITY_GROUP_ID"
echo "⚖️  Load Balancer: $ALB_DNS"
echo "🎯 Target Group: $TARGET_GROUP_ARN"
echo "📁 Log Group: $LOG_GROUP_NAME"
echo ""
echo "🔗 ALB Console: https://$AWS_REGION.console.aws.amazon.com/ec2/home?region=$AWS_REGION#LoadBalancer:search=$ALB_NAME"
echo ""

log_success "스크립트 실행 완료! 다음 단계: ./3-deploy-ecs-service.sh"