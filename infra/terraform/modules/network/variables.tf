# ========================================
# Network 모듈 입력 변수
# ========================================
# 학습 포인트: Phase 2에서는 기존 인프라를 참조
# Phase 3+에서 실제 VPC, ALB 등을 생성하는 코드로 확장 예정

variable "vpc_id" {
  description = "기존 VPC ID (data source 조회용)"
  type        = string
}

variable "subnet_ids" {
  description = "기존 서브넷 ID 목록 (data source 조회용)"
  type        = list(string)
}

variable "security_group_id" {
  description = "기존 보안 그룹 ID (data source 조회용)"
  type        = string
}

variable "target_group_arn" {
  description = "기존 Target Group ARN (data source 조회용)"
  type        = string
}
