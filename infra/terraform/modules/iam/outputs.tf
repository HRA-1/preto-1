# ========================================
# IAM 모듈 출력값
# ========================================
output "task_execution_role_arn" {
  description = "Task Execution Role ARN"
  value       = aws_iam_role.ecs_task_execution.arn
}

output "task_execution_role_name" {
  description = "Task Execution Role 이름"
  value       = aws_iam_role.ecs_task_execution.name
}

output "task_role_arn" {
  description = "Task Role ARN"
  value       = aws_iam_role.ecs_task.arn
}

output "task_role_name" {
  description = "Task Role 이름"
  value       = aws_iam_role.ecs_task.name
}
