# ========================================
# 기존 네트워크 인프라 참조
# ========================================
# 학습 포인트: Phase 2에서는 기존 Bash 스크립트로 생성한 인프라 참조
# 추후 Phase 3+에서 이 모듈을 확장하여 실제 VPC, ALB 등을 생성 가능

data "aws_vpc" "this" {
  id = var.vpc_id
}

data "aws_subnets" "this" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.this.id]
  }

  filter {
    name   = "subnet-id"
    values = var.subnet_ids
  }
}

data "aws_security_group" "this" {
  id = var.security_group_id
}

data "aws_lb_target_group" "this" {
  arn = var.target_group_arn
}
