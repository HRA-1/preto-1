# ========================================
# ECR 출력값
# ========================================
output "ecr_repository_url" {
  description = "ECR 리포지토리 URL"
  value       = aws_ecr_repository.app.repository_url
}

output "ecr_repository_name" {
  description = "ECR 리포지토리 이름"
  value       = aws_ecr_repository.app.name
}

# ========================================
# ECS 출력값
# ========================================
output "ecs_cluster_name" {
  description = "ECS 클러스터 이름"
  value       = aws_ecs_cluster.main.name
}

output "ecs_cluster_arn" {
  description = "ECS 클러스터 ARN"
  value       = aws_ecs_cluster.main.arn
}

output "ecs_service_name" {
  description = "ECS 서비스 이름"
  value       = aws_ecs_service.app.name
}

output "ecs_task_definition_family" {
  description = "ECS Task Definition Family"
  value       = aws_ecs_task_definition.app.family
}

output "ecs_task_definition_revision" {
  description = "ECS Task Definition 최신 리비전"
  value       = aws_ecs_task_definition.app.revision
}

# ========================================
# IAM 출력값
# ========================================
output "task_execution_role_arn" {
  description = "Task Execution Role ARN"
  value       = aws_iam_role.ecs_task_execution.arn
}

output "task_role_arn" {
  description = "Task Role ARN"
  value       = aws_iam_role.ecs_task.arn
}

# ========================================
# CloudWatch Logs 출력값
# ========================================
output "log_group_name" {
  description = "CloudWatch Logs 그룹 이름"
  value       = aws_cloudwatch_log_group.app.name
}

# ========================================
# 기존 인프라 정보
# ========================================
# 학습 포인트: data source로 조회한 정보도 output으로 노출 가능
# Terraform 외부에서 생성된 리소스 정보를 다른 모듈이나 스크립트에서 사용 가능
output "alb_dns_name" {
  description = "ALB DNS 이름 (애플리케이션 접속 URL)"
  value       = "preto-streamlit-app-alb-77728036.ap-northeast-2.elb.amazonaws.com"
}

output "vpc_id" {
  description = "VPC ID"
  value       = data.aws_vpc.main.id
}

output "subnet_ids" {
  description = "서브넷 ID 목록"
  value       = data.aws_subnets.main.ids
}
