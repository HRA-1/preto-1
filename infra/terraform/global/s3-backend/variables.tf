# ========================================
# Variables for S3 Backend
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

variable "bucket_name" {
  description = "Terraform State를 저장할 S3 버킷 이름 (전역 고유)"
  type        = string
  default     = "preto-terraform-state"
}
