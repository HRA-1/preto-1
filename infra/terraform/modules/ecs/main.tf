# ========================================
# ECS 클러스터
# ========================================
resource "aws_ecs_cluster" "this" {
  name = var.cluster_name

  tags = merge(
    var.tags,
    {
      Name = var.cluster_name
    }
  )
}

# ========================================
# CloudWatch Logs
# ========================================
resource "aws_cloudwatch_log_group" "this" {
  name              = var.log_group_name
  retention_in_days = 14

  tags = merge(
    var.tags,
    {
      Name = var.log_group_name
    }
  )
}

# ========================================
# ECS Task Definition
# ========================================
resource "aws_ecs_task_definition" "this" {
  family                   = var.task_family
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.cpu
  memory                   = var.memory

  execution_role_arn = var.task_execution_role_arn
  task_role_arn      = var.task_role_arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = var.cpu_architecture
  }

  container_definitions = jsonencode([
    {
      name      = var.container_name
      image     = var.container_image
      essential = true

      portMappings = [
        {
          containerPort = var.container_port
          protocol      = "tcp"
        }
      ]

      environment = [
        for key, value in var.environment_variables : {
          name  = key
          value = value
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.this.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  tags = merge(
    var.tags,
    {
      Name = "${var.task_family}-task-def"
    }
  )
}

# ========================================
# ECS 서비스
# ========================================
resource "aws_ecs_service" "this" {
  name            = var.service_name
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.this.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnets
    security_groups  = var.security_groups
    assign_public_ip = var.assign_public_ip
  }

  load_balancer {
    target_group_arn = var.target_group_arn
    container_name   = var.container_name
    container_port   = var.container_port
  }

  health_check_grace_period_seconds = var.health_check_grace_period

  tags = merge(
    var.tags,
    {
      Name = var.service_name
    }
  )
}
