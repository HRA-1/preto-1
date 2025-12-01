# ========================================
# ECR 출력값
# ========================================
output "ecr_repository_url" {
  description = "ECR 리포지토리 URL"
  value       = module.ecr.repository_url
}

output "ecr_repository_name" {
  description = "ECR 리포지토리 이름"
  value       = module.ecr.repository_name
}

# ========================================
# ECS 출력값
# ========================================
output "ecs_cluster_name" {
  description = "ECS 클러스터 이름"
  value       = module.ecs.cluster_name
}

output "ecs_cluster_arn" {
  description = "ECS 클러스터 ARN"
  value       = module.ecs.cluster_arn
}

output "ecs_service_name" {
  description = "ECS 서비스 이름"
  value       = module.ecs.service_name
}

output "ecs_task_definition_family" {
  description = "ECS Task Definition Family"
  value       = module.ecs.task_definition_family
}

output "ecs_task_definition_revision" {
  description = "ECS Task Definition 최신 리비전"
  value       = module.ecs.task_definition_revision
}

# ========================================
# IAM 출력값
# ========================================
output "task_execution_role_arn" {
  description = "Task Execution Role ARN"
  value       = module.iam.task_execution_role_arn
}

output "task_role_arn" {
  description = "Task Role ARN"
  value       = module.iam.task_role_arn
}

# ========================================
# CloudWatch Logs 출력값
# ========================================
output "log_group_name" {
  description = "CloudWatch Logs 그룹 이름"
  value       = module.ecs.log_group_name
}

# ========================================
# Network 출력값
# ========================================
output "vpc_id" {
  description = "VPC ID"
  value       = module.network.vpc_id
}

output "subnet_ids" {
  description = "서브넷 ID 목록"
  value       = module.network.subnet_ids
}

# ========================================
# ALB 정보 (하드코딩)
# ========================================
# 학습 포인트: 아직 ALB가 Terraform으로 관리되지 않으므로 임시로 하드코딩
# Phase 3+에서 ALB도 모듈화하면 동적으로 참조 가능
output "alb_dns_name" {
  description = "ALB DNS 이름 (애플리케이션 접속 URL)"
  value       = "preto-streamlit-app-alb-77728036.ap-northeast-2.elb.amazonaws.com"
}
