# ========================================
# Terraform 설정
# ========================================
terraform {
  required_version = ">= 1.10.0, < 2.0.0"  # S3 Native Locking 지원

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ========================================
# Provider 설정
# ========================================
provider "aws" {
  region = var.aws_region

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
# 학습 포인트: 모듈화된 구조에서도 locals로 일관된 이름 관리
locals {
  name_prefix = "${var.project_name}-${var.app_name}"

  common_tags = {
    Project     = var.project_name
    Application = var.app_name
    Environment = var.environment
  }
}

# ========================================
# Network 모듈
# ========================================
# 학습 포인트: 모듈을 사용하면 복잡한 네트워크 설정을 간단하게 참조
module "network" {
  source = "../../modules/network"

  vpc_id            = var.vpc_id
  subnet_ids        = var.subnet_ids
  security_group_id = var.security_group_id
  target_group_arn  = var.target_group_arn
}

# ========================================
# IAM 모듈
# ========================================
# 학습 포인트: IAM 역할을 모듈로 분리하여 재사용 가능
module "iam" {
  source = "../../modules/iam"

  name_prefix = local.name_prefix
  tags        = local.common_tags
}

# ========================================
# ECR 모듈
# ========================================
# 학습 포인트: ECR 설정을 모듈로 캡슐화
module "ecr" {
  source = "../../modules/ecr"

  repository_name         = local.name_prefix
  image_tag_mutability    = var.image_tag_mutability
  scan_on_push            = true
  lifecycle_policy_count  = var.ecr_lifecycle_count
  tags                    = local.common_tags
}

# ========================================
# ECS 모듈
# ========================================
# 학습 포인트: 모듈 간 의존성을 output/input으로 연결
module "ecs" {
  source = "../../modules/ecs"

  # 기본 정보
  cluster_name  = "${local.name_prefix}-cluster"
  service_name  = "${local.name_prefix}-service"
  task_family   = local.name_prefix
  container_name = "${local.name_prefix}-container"

  # 컨테이너 설정
  container_image = "${module.ecr.repository_url}:latest"
  container_port  = var.container_port

  environment_variables = {
    ENVIRONMENT = var.environment
  }

  # 리소스 할당
  cpu               = var.ecs_cpu
  memory            = var.ecs_memory
  cpu_architecture  = var.cpu_architecture

  # 서비스 설정
  desired_count              = var.ecs_desired_count
  health_check_grace_period  = 300

  # IAM (모듈 간 참조)
  task_execution_role_arn = module.iam.task_execution_role_arn
  task_role_arn           = module.iam.task_role_arn

  # 네트워킹 (모듈 간 참조)
  subnets          = module.network.subnet_ids
  security_groups  = [module.network.security_group_id]
  assign_public_ip = true

  # 로드 밸런서 (모듈 간 참조)
  target_group_arn = module.network.target_group_arn

  # CloudWatch Logs
  log_group_name = "/ecs/${local.name_prefix}"
  aws_region     = var.aws_region

  tags = local.common_tags
}
