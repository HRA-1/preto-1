# ========================================
# Network 모듈 출력값
# ========================================

output "vpc_id" {
  description = "VPC ID"
  value       = data.aws_vpc.this.id
}

output "vpc_cidr" {
  description = "VPC CIDR 블록"
  value       = data.aws_vpc.this.cidr_block
}

output "subnet_ids" {
  description = "서브넷 ID 목록"
  value       = data.aws_subnets.this.ids
}

output "security_group_id" {
  description = "보안 그룹 ID"
  value       = data.aws_security_group.this.id
}

# ========================================
# ALB 출력값
# ========================================
output "alb_arn" {
  description = "ALB ARN"
  value       = aws_lb.this.arn
}

output "alb_dns_name" {
  description = "ALB DNS 이름 (애플리케이션 접속 URL)"
  value       = aws_lb.this.dns_name
}

output "target_group_arn" {
  description = "Target Group ARN"
  value       = aws_lb_target_group.this.arn
}

output "target_group_name" {
  description = "Target Group 이름"
  value       = aws_lb_target_group.this.name
}
