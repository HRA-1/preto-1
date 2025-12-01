# ========================================
# IAM 모듈 입력 변수
# ========================================
variable "name_prefix" {
  description = "IAM 역할 이름 접두사"
  type        = string
}

variable "tags" {
  description = "리소스 태그"
  type        = map(string)
  default     = {}
}
