# ========================================
# S3 Backend Configuration (Dev)
# ========================================
# State를 S3에 저장하여 팀 협업 및 CI/CD 지원
# use_lockfile = true로 동시 수정 방지 (Terraform 1.10+)

terraform {
  backend "s3" {
    bucket       = "preto-terraform-state"
    key          = "dev/terraform.tfstate" # Prod와 다른 경로
    region       = "ap-northeast-2"
    encrypt      = true
    use_lockfile = true # S3 Native Locking (DynamoDB 불필요)
  }
}
