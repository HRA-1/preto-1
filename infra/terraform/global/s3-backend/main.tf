# ========================================
# S3 Backend Infrastructure
# ========================================
# Terraform State를 저장할 S3 버킷 생성
# DynamoDB 불필요 - Terraform 1.10+의 S3 Native Locking 사용

terraform {
  required_version = ">= 1.10.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = var.project_name
      ManagedBy = "Terraform"
      Purpose   = "Terraform State Backend"
    }
  }
}

# ========================================
# S3 Bucket for Terraform State
# ========================================
resource "aws_s3_bucket" "terraform_state" {
  bucket = var.bucket_name

  # State 버킷 실수 삭제 방지
  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name = var.bucket_name
  }
}

# 버전 관리 활성화 - State 히스토리 보존 및 롤백 지원
resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  versioning_configuration {
    status = "Enabled"
  }
}

# 서버 측 암호화 - State 파일에 민감 정보 포함 가능
resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Public Access 완전 차단
resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ========================================
# 참고: DynamoDB 불필요
# ========================================
# Terraform 1.10+에서 use_lockfile = true 설정 시
# S3에 .tflock 파일을 생성하여 동시 수정 방지
# 별도 DynamoDB 테이블 없이 State Locking 가능
