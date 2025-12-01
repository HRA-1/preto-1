# ========================================
# Task Execution Role Trust Policy
# ========================================
data "aws_iam_policy_document" "ecs_task_execution_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

# ========================================
# Task Execution Role
# ========================================
# 학습 포인트: ECS 에이전트가 사용하는 역할
# ECR에서 이미지 pull, CloudWatch Logs 작성 권한 필요
resource "aws_iam_role" "ecs_task_execution" {
  name               = "${var.name_prefix}-exec-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_execution_assume_role.json

  tags = merge(
    var.tags,
    {
      Name = "${var.name_prefix}-exec-role"
    }
  )
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ========================================
# Task Role Trust Policy
# ========================================
data "aws_iam_policy_document" "ecs_task_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

# ========================================
# Task Role
# ========================================
# 학습 포인트: 컨테이너 애플리케이션이 사용하는 역할
# 애플리케이션이 AWS SDK로 다른 AWS 서비스 호출 시 필요
resource "aws_iam_role" "ecs_task" {
  name               = "${var.name_prefix}-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role.json

  tags = merge(
    var.tags,
    {
      Name = "${var.name_prefix}-task-role"
    }
  )
}
