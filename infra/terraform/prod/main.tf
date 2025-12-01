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
  region = var.aws_region

  # 학습 포인트: default_tags를 사용하면 모든 리소스에 자동으로 태그 적용
  # 수동으로 각 리소스마다 태그를 추가할 필요가 없어 관리가 편함
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# ========================================
# Local Values
# ========================================
# 학습 포인트: locals는 반복되는 표현식을 변수처럼 재사용
# 리소스 이름 등을 일관되게 관리할 때 유용
locals {
  name_prefix = "${var.project_name}-${var.app_name}"
}

# ========================================
# ECR 리포지토리
# ========================================
resource "aws_ecr_repository" "app" {
  name = local.name_prefix

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
    Name = "${local.name_prefix}-ecr"
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
  name               = "${local.name_prefix}-exec-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_execution_assume_role.json

  tags = {
    Name = "${local.name_prefix}-exec-role"
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
  name               = "${local.name_prefix}-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role.json

  tags = {
    Name = "${local.name_prefix}-task-role"
  }
}

# ========================================
# Data Sources: 기존 인프라 참조
# ========================================
# 학습 포인트: data source를 통해 Terraform 외부에서 생성된 리소스 참조 가능
# 기존 Bash 스크립트로 생성한 VPC, 서브넷, 보안 그룹 등을 재사용

data "aws_vpc" "main" {
  id = var.vpc_id
}

data "aws_subnets" "main" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.main.id]
  }

  filter {
    name   = "subnet-id"
    values = var.subnet_ids
  }
}

data "aws_security_group" "app" {
  id = var.security_group_id
}

data "aws_lb_target_group" "app" {
  arn = var.target_group_arn
}

# ========================================
# CloudWatch Logs
# ========================================
resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${local.name_prefix}"
  retention_in_days = var.log_retention_days

  tags = {
    Name = "${local.name_prefix}-logs"
  }
}

# ========================================
# ECS 클러스터
# ========================================
# 학습 포인트: Fargate 모드에서는 클러스터 설정이 매우 간단
# EC2 모드와 달리 인스턴스 관리가 필요 없음
resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  tags = {
    Name = "${local.name_prefix}-cluster"
  }
}

# ========================================
# ECS Task Definition
# ========================================
# 학습 포인트: Task Definition은 컨테이너 실행 명세서
# - 어떤 이미지를 사용할지
# - CPU/메모리를 얼마나 할당할지
# - 어떤 포트를 열지
# - 로그를 어디에 쓸지
# 등을 정의
resource "aws_ecs_task_definition" "app" {
  family                   = local.name_prefix
  network_mode             = "awsvpc" # Fargate는 awsvpc 필수
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.ecs_cpu
  memory                   = var.ecs_memory

  # IAM 역할 연결
  execution_role_arn = aws_iam_role.ecs_task_execution.arn
  task_role_arn      = aws_iam_role.ecs_task.arn

  # 학습 포인트: ARM64 아키텍처 사용으로 비용 절감 (x86 대비 ~20% 저렴)
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  # 컨테이너 정의
  container_definitions = jsonencode([
    {
      name      = "${local.name_prefix}-container"
      image     = "${aws_ecr_repository.app.repository_url}:latest"
      essential = true

      portMappings = [
        {
          containerPort = var.container_port
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "ENVIRONMENT"
          value = var.environment
        }
      ]

      # 학습 포인트: awslogs 드라이버로 CloudWatch Logs와 자동 연동
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.app.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  tags = {
    Name = "${local.name_prefix}-task-def"
  }
}

# ========================================
# ECS 서비스
# ========================================
# 학습 포인트: ECS Service는 Task Definition을 실제로 실행하고 유지
# - 원하는 태스크 수 유지 (desired count)
# - 장애 발생 시 자동으로 새 태스크 시작
# - ALB와 연동하여 트래픽 분산
resource "aws_ecs_service" "app" {
  name            = "${local.name_prefix}-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.ecs_desired_count
  launch_type     = "FARGATE"

  # 학습 포인트: Fargate는 awsvpc 네트워크 모드 사용
  # 각 태스크가 독립적인 ENI를 가지며 VPC 내에서 실행
  network_configuration {
    subnets          = data.aws_subnets.main.ids
    security_groups  = [data.aws_security_group.app.id]
    assign_public_ip = true # 퍼블릭 서브넷에서 실행 시 필요
  }

  # 학습 포인트: ALB와 연동 설정
  # Target Group에 태스크를 자동 등록/해제
  load_balancer {
    target_group_arn = data.aws_lb_target_group.app.arn
    container_name   = "${local.name_prefix}-container"
    container_port   = var.container_port
  }

  # 학습 포인트: 헬스체크 유예 시간
  # 컨테이너 시작 후 헬스체크 실패를 무시할 시간 (초)
  # 애플리케이션 초기화 시간을 고려하여 설정
  health_check_grace_period_seconds = var.health_check_grace_period

  # 학습 포인트: 서비스 업데이트 시 ALB 헬스체크 완료를 기다림
  # 새 태스크가 healthy 상태가 된 후 이전 태스크 종료
  depends_on = [aws_iam_role_policy_attachment.ecs_task_execution]

  tags = {
    Name = "${local.name_prefix}-service"
  }
}
