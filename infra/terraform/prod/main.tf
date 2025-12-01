# ========================================
# Terraform 설정
# ========================================
terraform {
  # Terraform 버전 제약: 1.5.0 이상, 2.0.0 미만
  required_version = ">= 1.5.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      # ~> 5.0: 5.x의 최신 버전 사용, 6.0은 제외
      # 학습 포인트: 호환성 유지하면서 보안 패치 자동 적용
      version = "~> 5.0"
    }
  }
}

# ========================================
# Provider 설정
# ========================================
provider "aws" {
  region = "ap-northeast-2"

  # 학습 포인트: default_tags를 사용하면 모든 리소스에 자동으로 태그 적용
  # 수동으로 각 리소스마다 태그를 추가할 필요가 없어 관리가 편함
  default_tags {
    tags = {
      Project     = "preto"
      Environment = "prod"
      ManagedBy   = "Terraform"
    }
  }
}

# ========================================
# ECR 리포지토리
# ========================================
resource "aws_ecr_repository" "app" {
  name = "preto-streamlit-app"

  # 이미지 태그 변경 가능 여부
  # MUTABLE: latest 태그를 덮어쓸 수 있음 (개발 환경에 유용)
  # IMMUTABLE: 한번 푸시된 태그는 변경 불가 (프로덕션 권장)
  image_tag_mutability = "MUTABLE"

  # 이미지 스캔 설정
  # 학습 포인트: 푸시 시 자동으로 보안 취약점 스캔
  image_scanning_configuration {
    scan_on_push = true
  }

  # 이미지 암호화
  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "preto-streamlit-app-ecr"
  }
}

# ECR Lifecycle 정책: 오래된 이미지 자동 삭제
resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "최신 2개 이미지만 유지"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 2
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
