# ========================================
# ECS 모듈 출력값
# ========================================
output "cluster_id" {
  description = "ECS 클러스터 ID"
  value       = aws_ecs_cluster.this.id
}

output "cluster_arn" {
  description = "ECS 클러스터 ARN"
  value       = aws_ecs_cluster.this.arn
}

output "cluster_name" {
  description = "ECS 클러스터 이름"
  value       = aws_ecs_cluster.this.name
}

output "service_id" {
  description = "ECS 서비스 ID"
  value       = aws_ecs_service.this.id
}

output "service_name" {
  description = "ECS 서비스 이름"
  value       = aws_ecs_service.this.name
}

output "task_definition_arn" {
  description = "Task Definition ARN"
  value       = aws_ecs_task_definition.this.arn
}

output "task_definition_family" {
  description = "Task Definition Family"
  value       = aws_ecs_task_definition.this.family
}

output "task_definition_revision" {
  description = "Task Definition 리비전"
  value       = aws_ecs_task_definition.this.revision
}

output "log_group_name" {
  description = "CloudWatch Logs 그룹 이름"
  value       = aws_cloudwatch_log_group.this.name
}

output "log_group_arn" {
  description = "CloudWatch Logs 그룹 ARN"
  value       = aws_cloudwatch_log_group.this.arn
}
