# ========================================
# 프로젝트 기본 정보
# ========================================
variable "aws_region" {
  description = "AWS 리전"
  type        = string
  default     = "ap-northeast-2"
}

variable "project_name" {
  description = "프로젝트 이름"
  type        = string
  default     = "preto"
}

variable "app_name" {
  description = "애플리케이션 이름"
  type        = string
  default     = "streamlit-app-dev" # Dev 환경 구분
}

variable "environment" {
  description = "환경 (dev, staging, prod)"
  type        = string
  default     = "dev"
}

# ========================================
# ECR 설정
# ========================================
variable "image_tag_mutability" {
  description = "이미지 태그 변경 가능 여부"
  type        = string
  default     = "MUTABLE"
}

variable "ecr_lifecycle_count" {
  description = "보존할 이미지 개수"
  type        = number
  default     = 3 # Prod: 2, Dev: 10
}

# ========================================
# ECS 설정 (Dev는 작은 리소스)
# ========================================
variable "ecs_cpu" {
  description = "ECS 태스크 CPU"
  type        = string
  default     = "512" # Prod: 2048, Dev: 512
}

variable "ecs_memory" {
  description = "ECS 태스크 메모리 (MB)"
  type        = string
  default     = "1024" # Prod: 8192, Dev: 1024
}

variable "ecs_desired_count" {
  description = "실행할 태스크 수"
  type        = number
  default     = 1
}

variable "container_port" {
  description = "컨테이너 포트"
  type        = number
  default     = 8501
}

variable "cpu_architecture" {
  description = "CPU 아키텍처"
  type        = string
  default     = "ARM64"
}

# ========================================
# 기존 인프라 참조
# ========================================
# 주의: Dev 환경은 별도 VPC/ALB 구성 권장
# 현재는 Prod와 동일한 인프라 참조 (학습 목적)
variable "vpc_id" {
  description = "기존 VPC ID"
  type        = string
  default     = "vpc-0c11696cf8468ca8e"
}

variable "subnet_ids" {
  description = "기존 서브넷 ID 목록"
  type        = list(string)
  default = [
    "subnet-0cd2fcdff481b49c2",
    "subnet-0892735c449ac40db"
  ]
}

variable "security_group_id" {
  description = "기존 보안 그룹 ID"
  type        = string
  default     = "sg-0193a7c1c72f2a43c"
}
