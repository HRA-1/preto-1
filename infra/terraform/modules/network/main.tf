# ========================================
# 기존 네트워크 인프라 참조
# ========================================
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

# ========================================
# Application Load Balancer
# ========================================
resource "aws_lb" "this" {
  name               = "${var.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [data.aws_security_group.this.id]
  subnets            = data.aws_subnets.this.ids

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-alb"
  })
}

# ========================================
# Target Group
# ========================================
resource "aws_lb_target_group" "this" {
  name        = "${var.name_prefix}-tg"
  port        = var.container_port
  protocol    = "HTTP"
  vpc_id      = data.aws_vpc.this.id
  target_type = "ip"  # Fargate는 IP 타입 필수

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 30
    interval            = 60
    path                = var.health_check_path
    protocol            = "HTTP"
    matcher             = "200-399"
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-tg"
  })
}

# ========================================
# ALB Listener (HTTP)
# ========================================
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.this.arn
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-listener"
  })
}
