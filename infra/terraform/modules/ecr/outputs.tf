# ========================================
# ECR 모듈 출력값
# ========================================
output "repository_url" {
  description = "ECR 리포지토리 URL"
  value       = aws_ecr_repository.this.repository_url
}

output "repository_arn" {
  description = "ECR 리포지토리 ARN"
  value       = aws_ecr_repository.this.arn
}

output "repository_name" {
  description = "ECR 리포지토리 이름"
  value       = aws_ecr_repository.this.name
}

output "registry_id" {
  description = "ECR 레지스트리 ID"
  value       = aws_ecr_repository.this.registry_id
}
