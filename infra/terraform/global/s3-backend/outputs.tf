# ========================================
# Outputs for S3 Backend
# ========================================

output "bucket_name" {
  description = "Terraform State S3 버킷 이름"
  value       = aws_s3_bucket.terraform_state.id
}

output "bucket_arn" {
  description = "Terraform State S3 버킷 ARN"
  value       = aws_s3_bucket.terraform_state.arn
}

output "bucket_region" {
  description = "S3 버킷 리전"
  value       = var.aws_region
}

# Backend 설정 시 사용할 값들 출력
output "backend_config" {
  description = "environments/*/backend.tf에서 사용할 설정값"
  value = {
    bucket       = aws_s3_bucket.terraform_state.id
    region       = var.aws_region
    encrypt      = true
    use_lockfile = true
  }
}
