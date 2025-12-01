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

# ========================================
# IAM 역할: Task Execution Role
# ========================================
# Task Execution Role: ECS 에이전트가 사용
# - ECR에서 이미지 pull
# - CloudWatch Logs에 로그 작성
# - Secrets Manager에서 시크릿 읽기 (필요 시)

# Trust Policy: 어떤 AWS 서비스가 이 역할을 assume 할 수 있는지 정의
data "aws_iam_policy_document" "ecs_task_execution_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "ecs_task_execution" {
  name               = "preto-streamlit-app-exec-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_execution_assume_role.json

  tags = {
    Name = "preto-streamlit-app-exec-role"
  }
}

# AWS 관리형 정책 연결
# AmazonECSTaskExecutionRolePolicy: ECR pull, CloudWatch Logs 권한 포함
resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ========================================
# IAM 역할: Task Role
# ========================================
# Task Role: 컨테이너 내 애플리케이션이 사용
# - 애플리케이션이 AWS SDK를 통해 AWS 서비스 호출 시 사용
# - 현재는 권한 없음, 필요 시 정책 추가 (예: S3, DynamoDB 접근)

data "aws_iam_policy_document" "ecs_task_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "ecs_task" {
  name               = "preto-streamlit-app-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role.json

  tags = {
    Name = "preto-streamlit-app-task-role"
  }
}
