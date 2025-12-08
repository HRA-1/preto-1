# ========================================
# Network 모듈 입력 변수
# ========================================

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "subnet_ids" {
  description = "서브넷 ID 목록"
  type        = list(string)
}

variable "security_group_id" {
  description = "보안 그룹 ID"
  type        = string
}

variable "name_prefix" {
  description = "리소스 이름 접두사"
  type        = string
}

variable "container_port" {
  description = "컨테이너 포트 (Target Group 용)"
  type        = number
  default     = 8501
}

variable "health_check_path" {
  description = "헬스체크 경로"
  type        = string
  default     = "/"
}

variable "tags" {
  description = "리소스 태그"
  type        = map(string)
  default     = {}
}
