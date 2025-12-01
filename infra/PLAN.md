# Terraform + GitHub Actions 마이그레이션 계획

## 📋 목표

Bash 스크립트 기반 인프라를 **Terraform + GitHub Actions**로 전환하여 코드로 관리되는 자동화된 배포 파이프라인 구축

## 🎓 학습 목표

이 프로젝트는 **학습 목적**으로 진행되며, 다음 원칙을 따릅니다:

1. **점진적 구현**: MVP부터 시작하여 단계적으로 기능 추가
2. **명확한 커밋**: 각 커밋은 하나의 기능/개선사항을 포함
3. **풍부한 주석**: 코드에 "무엇"보다 "왜"를 설명하는 주석 포함
4. **실용적 접근**: 꼭 필요한 기능부터 구현, 과도한 추상화 지양

## 🎯 선택한 기술 스택

### IaC: Terraform

**선택 이유:**
- 성숙한 생태계 및 커뮤니티
- HCL 문법이 선언적이고 명확
- State 파일 관리 유연성 (S3 + DynamoDB)
- 멀티클라우드 지원 (향후 확장 가능)
- 풍부한 AWS 프로바이더 지원

### CI/CD: GitHub Actions

**선택 이유:**
- Git 기반 워크플로우와 자연스러운 통합
- AWS OIDC 연동으로 보안 강화 (시크릿 불필요)
- 무료 티어 충분 (Public 리포지토리)
- 풍부한 액션 생태계
- 환경 보호 및 승인 프로세스 내장

## 📁 최종 프로젝트 구조 (Phase 5 완료 후)

```
preto-1/
├── infra/
│   ├── terraform/
│   │   ├── prod/                      # 프로덕션 환경 (Phase 1에서 시작)
│   │   │   ├── main.tf                # 메인 리소스 정의
│   │   │   ├── variables.tf           # 변수 정의
│   │   │   ├── terraform.tfvars       # 변수 값
│   │   │   ├── outputs.tf             # 출력 값
│   │   │   ├── versions.tf            # Provider 버전
│   │   │   └── backend.tf             # S3 백엔드 (Phase 3 추가)
│   │   ├── modules/                   # 재사용 모듈 (Phase 2 추가)
│   │   │   ├── networking/
│   │   │   │   ├── main.tf
│   │   │   │   ├── variables.tf
│   │   │   │   ├── outputs.tf
│   │   │   │   └── README.md
│   │   │   ├── ecr/
│   │   │   ├── iam/
│   │   │   └── ecs-fargate/
│   │   ├── dev/                       # Dev 환경 (Phase 3 추가)
│   │   ├── global/                    # 글로벌 리소스 (Phase 3 추가)
│   │   │   └── s3-backend/
│   │   └── scripts/
│   └── ecs-legacy/                    # 기존 스크립트 (백업)
├── .github/
│   └── workflows/                     # CI/CD (Phase 4 추가)
│       ├── terraform-plan.yml
│       ├── terraform-apply.yml
│       └── docker-build.yml
├── .gitignore
└── README.md
```

## 🎯 점진적 구현 전략

### Phase 1: MVP - Monolithic 단일 파일 (Day 1-2)

**목표**: 가장 간단한 형태로 Terraform 동작 확인

**구조**:
```
infra/terraform/prod/
├── main.tf              # 모든 리소스를 하나의 파일에
├── variables.tf         # 필수 변수만
├── terraform.tfvars     # 실제 값
└── outputs.tf           # 주요 출력값만
```

**포함 리소스**:
- ECR 리포지토리
- IAM 역할 (Task Execution, Task Role)
- ECS 클러스터
- ECS Task Definition (간단한 버전)
- ECS 서비스 (기본 설정만)
- 기존 VPC/서브넷/ALB 참조 (Data Source)

**제외 항목**:
- ❌ 모듈화
- ❌ S3 Backend (Local state 사용)
- ❌ Auto Scaling
- ❌ CloudWatch 알림
- ❌ 환경 분리

**학습 포인트**:
- Terraform 기본 문법
- Resource vs Data Source
- 변수 활용
- 출력값 확인

**커밋 전략**:
1. `feat: add terraform basic structure and gitignore`
2. `feat: add ECR repository configuration`
3. `feat: add IAM roles for ECS tasks`
4. `feat: add ECS cluster and task definition`
5. `feat: add ECS service with ALB integration`
6. `docs: add Phase 1 README`

---

### Phase 2: 모듈화 (Day 3-4)

**목표**: 재사용 가능한 모듈로 분리

**변경사항**:
- `main.tf` → 모듈 호출로 변경
- 4개 모듈 생성: networking, ecr, iam, ecs-fargate
- 각 모듈에 README.md 추가

**학습 포인트**:
- 모듈 개념과 필요성
- 모듈 간 의존성 관리 (outputs → inputs)
- 변수 전달 방식
- 모듈 재사용성

**커밋 전략**:
1. `refactor: extract ECR into module`
2. `refactor: extract IAM into module`
3. `refactor: extract networking data sources into module`
4. `refactor: extract ECS into module`
5. `refactor: update main.tf to use modules`
6. `docs: add module documentation`

---

### Phase 3: S3 Backend + 환경 분리 (Day 5-6)

**목표**: State 원격 관리 및 Dev/Prod 환경 분리

**추가 구조**:
```
infra/terraform/
├── global/s3-backend/   # State 저장용 인프라
├── dev/                 # Dev 환경
└── prod/                # Prod 환경 (기존)
```

**학습 포인트**:
- Terraform State의 중요성
- Backend 설정 방법
- State Locking (DynamoDB)
- 환경별 tfvars 관리

**커밋 전략**:
1. `feat: add S3 backend infrastructure`
2. `feat: migrate to S3 backend for prod`
3. `feat: add dev environment configuration`
4. `docs: add backend migration guide`

---

### Phase 4: CI/CD 자동화 (Day 7-8)

**목표**: GitHub Actions로 배포 자동화

**추가 파일**:
```
.github/workflows/
├── terraform-plan.yml   # PR에서 plan
├── terraform-apply.yml  # Main에서 apply
└── docker-build.yml     # 이미지 빌드 & 배포
```

**학습 포인트**:
- GitHub Actions 기본 개념
- AWS OIDC 인증
- Terraform with CI/CD
- PR 기반 워크플로우

**커밋 전략**:
1. `feat: add terraform plan workflow for PR`
2. `feat: add terraform apply workflow for main`
3. `feat: add docker build and deploy workflow`
4. `docs: add CI/CD setup guide`

---

### Phase 5: 고도화 (Day 9-10)

**목표**: 프로덕션 수준의 기능 추가

**추가 기능**:
- Auto Scaling (CPU/Memory 기반)
- CloudWatch 알람
- 상세한 로깅
- 보안 강화 (Secrets Manager 연동)

**학습 포인트**:
- ECS Auto Scaling 설정
- CloudWatch Metrics & Alarms
- 모니터링 Best Practices
- 보안 강화 방법

**커밋 전략**:
1. `feat: add auto scaling policies`
2. `feat: add CloudWatch alarms`
3. `feat: add enhanced logging configuration`
4. `feat: integrate with Secrets Manager`
5. `docs: add monitoring and operations guide`

## 📝 Phase 1 코드 예시 (학습용 주석 포함)

### main.tf (MVP - 모든 리소스 포함)

```hcl
# ========================================
# Terraform 설정
# ========================================
terraform {
  # Terraform 버전 제약: 1.6.0 이상, 2.0.0 미만
  # 학습 포인트: 버전을 고정하여 팀 간 일관성 보장
  required_version = ">= 1.6.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      # ~> 5.0: 5.x의 최신 버전 사용, 6.0은 제외
      # 학습 포인트: 호환성 유지하면서 보안 패치 자동 적용
      version = "~> 5.0"
    }
  }
}

# ========================================
# Provider 설정
# ========================================
provider "aws" {
  region = var.aws_region

  # 학습 포인트: default_tags를 사용하면 모든 리소스에 자동으로 태그 적용
  # 수동으로 각 리소스마다 태그를 추가할 필요가 없어 관리가 편함
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = "prod"
      ManagedBy   = "Terraform"
    }
  }
}

# ========================================
# 기존 리소스 참조 (Data Sources)
# ========================================
# 학습 포인트: Data Source는 Terraform이 관리하지 않는 기존 리소스를 참조
# resource는 생성/수정/삭제를 관리, data는 읽기만 가능

# 기존 VPC 참조
data "aws_vpc" "existing" {
  # 기존 Bash 스크립트에서 사용하던 VPC ID
  id = var.vpc_id
}

# 기존 서브넷 조회
data "aws_subnets" "existing" {
  # 학습 포인트: filter를 사용하여 조건에 맞는 리소스 검색
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.existing.id]
  }

  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

# 기존 ALB 참조
data "aws_lb" "existing" {
  # 기존 Bash 스크립트로 생성한 ALB
  arn = var.alb_arn
}

# 기존 Target Group 참조
data "aws_lb_target_group" "existing" {
  arn = var.target_group_arn
}

# 기존 보안 그룹 참조
data "aws_security_group" "existing" {
  id = var.security_group_id
}

# ========================================
# ECR 리포지토리
# ========================================
# 학습 포인트: ECR은 Docker 이미지를 저장하는 AWS의 컨테이너 레지스트리
resource "aws_ecr_repository" "app" {
  name = "${var.project_name}-${var.app_name}"

  # 이미지 태그 변경 가능 여부
  # MUTABLE: latest 태그를 덮어쓸 수 있음 (개발 환경에 유용)
  # IMMUTABLE: 한번 푸시된 태그는 변경 불가 (프로덕션 권장)
  image_tag_mutability = "MUTABLE"

  # 이미지 스캔 설정
  # 학습 포인트: 푸시 시 자동으로 보안 취약점 스캔
  image_scanning_configuration {
    scan_on_push = true
  }

  # 이미지 암호화
  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "${var.project_name}-${var.app_name}-ecr"
  }
}

# ECR Lifecycle 정책: 오래된 이미지 자동 삭제
# 학습 포인트: 스토리지 비용 절감을 위해 불필요한 이미지 정리
resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "최신 10개 이미지만 유지"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# ========================================
# IAM 역할: Task Execution Role
# ========================================
# 학습 포인트: ECS Task Execution Role은 ECS 에이전트가 사용
# - ECR에서 이미지 pull
# - CloudWatch Logs에 로그 작성
# - Secrets Manager에서 시크릿 읽기

# Trust Policy: 누가 이 역할을 맡을 수 있는지 정의
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

resource "aws_iam_role" "ecs_task_execution" {
  name               = "${var.project_name}-${var.app_name}-exec-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_execution_assume_role.json

  tags = {
    Name = "${var.project_name}-${var.app_name}-exec-role"
  }
}

# AWS 관리형 정책 연결
# 학습 포인트: AWS가 미리 만들어둔 정책을 사용하면 편리하고 안전
resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ========================================
# IAM 역할: Task Role
# ========================================
# 학습 포인트: Task Role은 컨테이너 내 애플리케이션이 사용
# - 애플리케이션이 AWS 서비스에 접근할 때 필요
# - 현재는 권한이 없지만, 나중에 S3/DynamoDB 접근 시 추가 가능

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

resource "aws_iam_role" "ecs_task" {
  name               = "${var.project_name}-${var.app_name}-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role.json

  tags = {
    Name = "${var.project_name}-${var.app_name}-task-role"
  }
}

# ========================================
# CloudWatch Logs
# ========================================
# 학습 포인트: ECS 컨테이너의 stdout/stderr을 CloudWatch로 전송
resource "aws_cloudwatch_log_group" "app" {
  name = "/ecs/${var.project_name}-${var.app_name}"

  # 로그 보존 기간 (일)
  # 학습 포인트: 보존 기간을 설정하여 스토리지 비용 관리
  retention_in_days = 14

  tags = {
    Name = "${var.project_name}-${var.app_name}-logs"
  }
}

# ========================================
# ECS 클러스터
# ========================================
# 학습 포인트: ECS 클러스터는 컨테이너를 실행하는 논리적 그룹
# Fargate를 사용하므로 EC2 인스턴스 관리 불필요
resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-${var.app_name}-cluster"

  # Container Insights로 메트릭 수집 (추가 비용 발생)
  # Phase 5에서 모니터링 강화 시 활성화 예정
  setting {
    name  = "containerInsights"
    value = "disabled"
  }

  tags = {
    Name = "${var.project_name}-${var.app_name}-cluster"
  }
}

# ========================================
# ECS Task Definition
# ========================================
# 학습 포인트: Task Definition은 컨테이너 실행 방법을 정의 (Docker Compose와 유사)
resource "aws_ecs_task_definition" "app" {
  family = "${var.project_name}-${var.app_name}"

  # Fargate: 서버리스 컨테이너, EC2 관리 불필요
  requires_compatibilities = ["FARGATE"]

  # awsvpc: 각 태스크가 독립적인 ENI(네트워크 인터페이스)를 가짐
  network_mode = "awsvpc"

  # CPU와 메모리는 Fargate의 정해진 조합만 가능
  # 2048 CPU (2 vCPU), 8192 MB (8 GB)
  cpu    = var.task_cpu
  memory = var.task_memory

  # IAM 역할 연결
  execution_role_arn = aws_iam_role.ecs_task_execution.arn
  task_role_arn      = aws_iam_role.ecs_task.arn

  # ARM64 아키텍처 사용 (비용 절감)
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  # 컨테이너 정의 (JSON 형식)
  # 학습 포인트: jsonencode를 사용하여 HCL 문법으로 JSON 작성 가능
  container_definitions = jsonencode([
    {
      name  = var.container_name
      image = "${aws_ecr_repository.app.repository_url}:latest"

      # 필수 컨테이너: 이 컨테이너가 종료되면 태스크 전체가 종료
      essential = true

      # 포트 매핑
      portMappings = [
        {
          containerPort = var.container_port
          protocol      = "tcp"
        }
      ]

      # CloudWatch Logs 설정
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.app.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }

      # 환경 변수
      environment = [
        {
          name  = "ENVIRONMENT"
          value = "prod"
        }
      ]
    }
  ])

  tags = {
    Name = "${var.project_name}-${var.app_name}-task"
  }
}

# ========================================
# ECS 서비스
# ========================================
# 학습 포인트: ECS 서비스는 Task Definition을 기반으로 컨테이너를 실행하고 유지
resource "aws_ecs_service" "app" {
  name            = "${var.project_name}-${var.app_name}-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn

  # 원하는 태스크 수 (현재는 1개)
  desired_count = var.desired_count

  # Fargate 사용
  launch_type = "FARGATE"

  # 네트워크 설정
  network_configuration {
    # 기존 서브넷 사용
    subnets = data.aws_subnets.existing.ids

    # 기존 보안 그룹 사용
    security_groups = [data.aws_security_group.existing.id]

    # Public IP 할당 (인터넷 접근 필요)
    # 학습 포인트: NAT Gateway 없이 인터넷 접근하려면 필요
    assign_public_ip = true
  }

  # ALB 연결
  load_balancer {
    target_group_arn = data.aws_lb_target_group.existing.arn
    container_name   = var.container_name
    container_port   = var.container_port
  }

  # 헬스체크 유예 시간 (초)
  # 학습 포인트: 컨테이너 시작 후 헬스체크를 시작하기 전 대기 시간
  # 애플리케이션 초기화 시간을 고려하여 설정
  health_check_grace_period_seconds = 300

  # 배포 설정
  # 학습 포인트: 롤링 업데이트 시 최소/최대 태스크 수
  deployment_configuration {
    maximum_percent         = 200  # 배포 중 최대 200% (2개)까지 실행 가능
    minimum_healthy_percent = 100  # 최소 100% (1개)는 항상 실행 중
  }

  # 학습 포인트: depends_on을 명시하여 리소스 생성 순서 보장
  # ALB Listener가 먼저 생성된 후 서비스 생성
  depends_on = [
    aws_iam_role_policy_attachment.ecs_task_execution
  ]

  tags = {
    Name = "${var.project_name}-${var.app_name}-service"
  }
}
```

### variables.tf (변수 정의)

```hcl
# ========================================
# 기본 설정
# ========================================
variable "project_name" {
  description = "프로젝트 이름 (리소스 이름 prefix로 사용)"
  type        = string

  # 학습 포인트: validation을 통해 잘못된 값 입력 방지
  validation {
    condition     = length(var.project_name) > 0 && length(var.project_name) <= 20
    error_message = "프로젝트 이름은 1-20자 사이여야 합니다."
  }
}

variable "app_name" {
  description = "애플리케이션 이름"
  type        = string
  default     = "streamlit-app"
}

variable "aws_region" {
  description = "AWS 리전"
  type        = string
  default     = "ap-northeast-2"
}

# ========================================
# 기존 리소스 참조
# ========================================
# 학습 포인트: 기존 Bash 스크립트로 생성한 리소스의 ID/ARN
variable "vpc_id" {
  description = "기존 VPC ID"
  type        = string
}

variable "security_group_id" {
  description = "기존 보안 그룹 ID"
  type        = string
}

variable "alb_arn" {
  description = "기존 ALB ARN"
  type        = string
}

variable "target_group_arn" {
  description = "기존 Target Group ARN"
  type        = string
}

# ========================================
# ECS 설정
# ========================================
variable "task_cpu" {
  description = "Fargate Task CPU (256, 512, 1024, 2048, 4096)"
  type        = string
  default     = "2048"

  # 학습 포인트: Fargate는 정해진 CPU/메모리 조합만 허용
  validation {
    condition     = contains(["256", "512", "1024", "2048", "4096"], var.task_cpu)
    error_message = "유효한 Fargate CPU 값이 아닙니다."
  }
}

variable "task_memory" {
  description = "Fargate Task 메모리 (MB)"
  type        = string
  default     = "8192"

  validation {
    condition = contains([
      "512", "1024", "2048", "3072", "4096", "5120",
      "6144", "7168", "8192", "16384", "30720"
    ], var.task_memory)
    error_message = "유효한 Fargate 메모리 값이 아닙니다."
  }
}

variable "desired_count" {
  description = "실행할 태스크 수"
  type        = number
  default     = 1

  validation {
    condition     = var.desired_count >= 0 && var.desired_count <= 10
    error_message = "태스크 수는 0-10 사이여야 합니다."
  }
}

variable "container_name" {
  description = "컨테이너 이름"
  type        = string
  default     = "streamlit-app-container"
}

variable "container_port" {
  description = "컨테이너 포트"
  type        = number
  default     = 8501
}
```

### terraform.tfvars (실제 값)

```hcl
# ========================================
# 프로젝트 기본 정보
# ========================================
project_name = "preto"
app_name     = "streamlit-app"
aws_region   = "ap-northeast-2"

# ========================================
# 기존 리소스 참조
# 학습 포인트: infrastructure.env 파일의 값을 여기에 복사
# ========================================
vpc_id              = "vpc-0c11696cf8468ca8e"
security_group_id   = "sg-0193a7c1c72f2a43c"
alb_arn             = "arn:aws:elasticloadbalancing:ap-northeast-2:201023212334:loadbalancer/app/preto-streamlit-app-alb/68b1ff3c4e240935"
target_group_arn    = "arn:aws:elasticloadbalancing:ap-northeast-2:201023212334:targetgroup/preto-streamlit-app-tg/3e75a65e5bbcaa20"

# ========================================
# ECS 설정
# ========================================
task_cpu       = "2048"  # 2 vCPU
task_memory    = "8192"  # 8 GB
desired_count  = 1
container_name = "preto-streamlit-app-container"
container_port = 8501
```

### outputs.tf (출력 값)

```hcl
# 학습 포인트: Terraform 실행 후 중요한 정보를 출력
# terraform output 명령으로 확인 가능

output "ecr_repository_url" {
  description = "ECR 리포지토리 URL (Docker push에 사용)"
  value       = aws_ecr_repository.app.repository_url
}

output "ecs_cluster_name" {
  description = "ECS 클러스터 이름"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "ECS 서비스 이름"
  value       = aws_ecs_service.app.name
}

output "task_definition_arn" {
  description = "Task Definition ARN"
  value       = aws_ecs_task_definition.app.arn
}

output "cloudwatch_log_group" {
  description = "CloudWatch 로그 그룹 이름"
  value       = aws_cloudwatch_log_group.app.name
}

# 학습 포인트: 기존 리소스 정보도 출력 가능
output "alb_dns_name" {
  description = "Application Load Balancer DNS 이름"
  value       = data.aws_lb.existing.dns_name
}

output "application_url" {
  description = "애플리케이션 접속 URL"
  value       = "http://${data.aws_lb.existing.dns_name}"
}
```

### .gitignore

```gitignore
# ========================================
# Terraform
# ========================================
# 학습 포인트: State 파일에는 민감 정보가 포함될 수 있으므로 Git에 포함하지 않음
*.tfstate
*.tfstate.*
*.tfstate.backup

# Terraform 플러그인 디렉토리
.terraform/
.terraform.lock.hcl

# 로컬 환경 설정 파일
*.tfvars.local
override.tf
override.tf.json

# ========================================
# 민감 정보
# ========================================
*.pem
*.key
secrets.auto.tfvars

# ========================================
# OS
# ========================================
.DS_Store
Thumbs.db
```

## 🏗️ Terraform Best Practices

### 1. State 관리 (S3 + DynamoDB)

**S3 Backend 설정:**

```hcl
# environments/prod/backend.tf
terraform {
  backend "s3" {
    bucket         = "preto-terraform-state-prod"
    key            = "ecs/terraform.tfstate"
    region         = "ap-northeast-2"
    encrypt        = true
    dynamodb_table = "preto-terraform-locks"
  }
}
```

**장점:**
- 팀 협업 가능 (원격 state 공유)
- State locking으로 동시 수정 방지
- S3 버전 관리로 state 히스토리 추적
- 암호화로 민감 정보 보호

### 2. 모듈화 구조

**환경별 메인 파일 예시:**

```hcl
# environments/prod/main.tf
module "networking" {
  source = "../../modules/networking"

  project_name = var.project_name
  environment  = var.environment
  vpc_id       = var.vpc_id  # 기존 VPC 참조
  subnet_ids   = var.subnet_ids

  tags = local.common_tags
}

module "ecr" {
  source = "../../modules/ecr"

  repository_name      = "${var.project_name}-${var.app_name}"
  image_tag_mutability = "MUTABLE"
  scan_on_push         = true

  tags = local.common_tags
}

module "iam" {
  source = "../../modules/iam"

  project_name = var.project_name
  environment  = var.environment

  tags = local.common_tags
}

module "ecs_fargate" {
  source = "../../modules/ecs-fargate"

  # 모듈 간 의존성
  vpc_id              = module.networking.vpc_id
  subnet_ids          = module.networking.subnet_ids
  security_group_id   = module.networking.security_group_id
  target_group_arn    = module.networking.target_group_arn
  alb_dns_name        = module.networking.alb_dns_name

  ecr_repository_url  = module.ecr.repository_url
  task_execution_role_arn = module.iam.task_execution_role_arn
  task_role_arn       = module.iam.task_role_arn

  # ECS 설정
  cluster_name     = var.cluster_name
  service_name     = var.service_name
  task_family      = var.task_family
  container_name   = var.container_name

  task_cpu         = var.task_cpu
  task_memory      = var.task_memory
  desired_count    = var.desired_count
  container_port   = var.container_port

  # Auto Scaling
  enable_autoscaling       = var.enable_autoscaling
  autoscaling_min_capacity = var.autoscaling_min_capacity
  autoscaling_max_capacity = var.autoscaling_max_capacity

  tags = local.common_tags
}
```

### 3. 변수 관리 (Layered Variables)

**변수 정의:**

```hcl
# environments/prod/variables.tf
variable "project_name" {
  description = "Project name"
  type        = string

  validation {
    condition     = length(var.project_name) > 0 && length(var.project_name) <= 20
    error_message = "Project name must be between 1 and 20 characters."
  }
}

variable "task_cpu" {
  description = "Fargate task CPU units"
  type        = string
  default     = "2048"

  validation {
    condition     = contains(["256", "512", "1024", "2048", "4096"], var.task_cpu)
    error_message = "CPU must be a valid Fargate value."
  }
}

variable "task_memory" {
  description = "Fargate task memory in MB"
  type        = string
  default     = "8192"

  validation {
    condition = contains([
      "512", "1024", "2048", "3072", "4096", "5120",
      "6144", "7168", "8192", "16384", "30720"
    ], var.task_memory)
    error_message = "Memory must be a valid Fargate value."
  }
}

variable "tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default     = {}
}
```

**변수 값 설정:**

```hcl
# environments/prod/terraform.tfvars
project_name = "preto"
app_name     = "streamlit-app"
environment  = "prod"

aws_region     = "ap-northeast-2"
aws_account_id = "201023212334"

# 네트워킹 (기존 리소스 참조)
vpc_id     = "vpc-0c11696cf8468ca8e"
subnet_ids = ["subnet-0cd2fcdff481b49c2", "subnet-0892735c449ac40db"]

# ECS 설정
cluster_name   = "preto-streamlit-app-cluster"
service_name   = "preto-streamlit-app-service"
task_family    = "preto-streamlit-app"
container_name = "preto-streamlit-app-container"

task_cpu       = "2048"  # 2 vCPU
task_memory    = "8192"  # 8 GB
desired_count  = 1
container_port = 8501

# Auto Scaling
enable_autoscaling       = true
autoscaling_min_capacity = 1
autoscaling_max_capacity = 4
cpu_target_value         = 70
memory_target_value      = 80

# 태깅
tags = {
  Project     = "preto"
  Environment = "prod"
  ManagedBy   = "terraform"
  Repository  = "preto-1"
}
```

### 4. 버전 고정 (Version Pinning)

```hcl
# environments/prod/versions.tf
terraform {
  required_version = ">= 1.6.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"  # 5.x 최신, 6.0 미만
    }
  }
}

provider "aws" {
  region = var.aws_region

  # 모든 리소스에 기본 태그 자동 적용
  default_tags {
    tags = {
      ManagedBy   = "Terraform"
      Project     = var.project_name
      Environment = var.environment
    }
  }
}
```

### 5. 명명 규칙 (Naming Convention)

```hcl
# environments/prod/main.tf
locals {
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = merge(
    var.tags,
    {
      Name        = "${local.name_prefix}-${var.service_name}"
      Terraform   = "true"
      Repository  = "preto-1"
      LastUpdated = timestamp()
    }
  )
}

# 리소스 이름 예시:
# - preto-prod-cluster
# - preto-prod-streamlit-app-service
# - preto-prod-alb
# - preto-prod-tg
```

### 6. Data Sources (기존 리소스 참조)

```hcl
# modules/networking/main.tf

# 기존 VPC 참조 (import 대신)
data "aws_vpc" "existing" {
  id = var.vpc_id
}

# 기존 서브넷 참조
data "aws_subnets" "existing" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.existing.id]
  }

  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

# 기존 ALB 참조 (선택적)
data "aws_lb" "existing" {
  count = var.use_existing_alb ? 1 : 0
  arn   = var.existing_alb_arn
}
```

### 7. 출력 값 (Outputs)

```hcl
# environments/prod/outputs.tf
output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = module.ecr.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.ecs_fargate.cluster_name
}

output "ecs_service_name" {
  description = "ECS service name"
  value       = module.ecs_fargate.service_name
}

output "alb_dns_name" {
  description = "Application Load Balancer DNS name"
  value       = module.networking.alb_dns_name
}

output "application_url" {
  description = "Application URL"
  value       = "http://${module.networking.alb_dns_name}"
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group name"
  value       = module.ecs_fargate.log_group_name
}
```

### 8. 보안 Best Practices

**State 파일 암호화:**

```hcl
# global/s3-backend/main.tf
resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.terraform_state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

**.gitignore 설정:**

```gitignore
# Terraform
*.tfstate
*.tfstate.*
*.tfstate.backup
.terraform/
.terraform.lock.hcl
*.tfvars.local
override.tf
override.tf.json

# 민감 정보
*.pem
*.key
secrets.auto.tfvars
```

## 🔄 GitHub Actions Workflow

### 1. Terraform Plan (PR 자동 실행)

```yaml
# .github/workflows/terraform-plan.yml
name: Terraform Plan

on:
  pull_request:
    paths:
      - 'infra/terraform/**'
      - '.github/workflows/terraform-plan.yml'

permissions:
  id-token: write   # OIDC 토큰
  contents: read
  pull-requests: write  # PR 코멘트

jobs:
  terraform-plan:
    name: Terraform Plan
    runs-on: ubuntu-latest

    strategy:
      matrix:
        environment: [dev, prod]

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Configure AWS Credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::201023212334:role/GitHubActionsRole
          aws-region: ap-northeast-2

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.6.0

      - name: Terraform Format Check
        working-directory: infra/terraform/environments/${{ matrix.environment }}
        run: terraform fmt -check -recursive

      - name: Terraform Init
        working-directory: infra/terraform/environments/${{ matrix.environment }}
        run: terraform init

      - name: Terraform Validate
        working-directory: infra/terraform/environments/${{ matrix.environment }}
        run: terraform validate

      - name: Terraform Plan
        id: plan
        working-directory: infra/terraform/environments/${{ matrix.environment }}
        run: |
          terraform plan -no-color -out=tfplan
          terraform show -no-color tfplan > plan_output.txt
        continue-on-error: true

      - name: Comment Plan on PR
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const plan = fs.readFileSync('infra/terraform/environments/${{ matrix.environment }}/plan_output.txt', 'utf8');

            const output = `#### Terraform Plan - \`${{ matrix.environment }}\` 📝

            <details><summary>Show Plan</summary>

            \`\`\`terraform
            ${plan}
            \`\`\`

            </details>

            *Pushed by: @${{ github.actor }}, Action: \`${{ github.event_name }}\`*`;

            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: output
            });

      - name: Check Plan Status
        if: steps.plan.outcome == 'failure'
        run: exit 1
```

### 2. Terraform Apply (Main 브랜치)

```yaml
# .github/workflows/terraform-apply.yml
name: Terraform Apply

on:
  push:
    branches: [main]
    paths:
      - 'infra/terraform/**'
      - '.github/workflows/terraform-apply.yml'

permissions:
  id-token: write
  contents: read

jobs:
  terraform-apply:
    name: Terraform Apply
    runs-on: ubuntu-latest
    environment: production  # 승인 프로세스

    strategy:
      matrix:
        environment: [prod]

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Configure AWS Credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::201023212334:role/GitHubActionsRole
          aws-region: ap-northeast-2

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.6.0

      - name: Terraform Init
        working-directory: infra/terraform/environments/${{ matrix.environment }}
        run: terraform init

      - name: Terraform Plan
        working-directory: infra/terraform/environments/${{ matrix.environment }}
        run: terraform plan -out=tfplan

      - name: Terraform Apply
        working-directory: infra/terraform/environments/${{ matrix.environment }}
        run: terraform apply -auto-approve tfplan

      - name: Output Results
        working-directory: infra/terraform/environments/${{ matrix.environment }}
        run: terraform output -json
```

### 3. Docker Build & Deploy

```yaml
# .github/workflows/docker-build.yml
name: Build and Deploy

on:
  push:
    branches: [main]
    paths:
      - 'app/**'
      - 'Dockerfile'
      - '.github/workflows/docker-build.yml'

permissions:
  id-token: write
  contents: read

jobs:
  build-and-push:
    name: Build and Push Docker Image
    runs-on: ubuntu-latest

    outputs:
      image-tag: ${{ steps.meta.outputs.tags }}

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::201023212334:role/GitHubActionsRole
          aws-region: ap-northeast-2

      - name: Login to ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Docker metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ steps.login-ecr.outputs.registry }}/preto-streamlit-app
          tags: |
            type=sha,prefix={{branch}}-
            type=raw,value=latest,enable={{is_default_branch}}
            type=semver,pattern={{version}}

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          platforms: linux/arm64

  deploy:
    name: Deploy to ECS
    needs: build-and-push
    runs-on: ubuntu-latest
    environment: production

    steps:
      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::201023212334:role/GitHubActionsRole
          aws-region: ap-northeast-2

      - name: Update ECS Service
        run: |
          aws ecs update-service \
            --cluster preto-streamlit-app-cluster \
            --service preto-streamlit-app-service \
            --force-new-deployment

      - name: Wait for deployment
        run: |
          aws ecs wait services-stable \
            --cluster preto-streamlit-app-cluster \
            --services preto-streamlit-app-service \
            --region ap-northeast-2

      - name: Get service status
        run: |
          aws ecs describe-services \
            --cluster preto-streamlit-app-cluster \
            --services preto-streamlit-app-service \
            --query 'services[0].[serviceName,status,runningCount,desiredCount]' \
            --output table
```

### 4. Destroy (수동 트리거)

```yaml
# .github/workflows/destroy.yml
name: Destroy Infrastructure

on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment to destroy'
        required: true
        type: choice
        options:
          - dev
          - prod
      confirm:
        description: 'Type "destroy" to confirm'
        required: true

permissions:
  id-token: write
  contents: read

jobs:
  destroy:
    name: Destroy Infrastructure
    runs-on: ubuntu-latest
    environment: ${{ github.event.inputs.environment }}

    steps:
      - name: Verify confirmation
        run: |
          if [ "${{ github.event.inputs.confirm }}" != "destroy" ]; then
            echo "Confirmation failed. You must type 'destroy' to proceed."
            exit 1
          fi

      - name: Checkout
        uses: actions/checkout@v4

      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::201023212334:role/GitHubActionsRole
          aws-region: ap-northeast-2

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.6.0

      - name: Terraform Init
        working-directory: infra/terraform/environments/${{ github.event.inputs.environment }}
        run: terraform init

      - name: Terraform Destroy
        working-directory: infra/terraform/environments/${{ github.event.inputs.environment }}
        run: terraform destroy -auto-approve
```

## 📅 단계별 구현 일정 (학습 중심)

### Phase 1: MVP - 단일 파일 구조 (Day 1-2)

**목표**: Terraform 기본 개념 익히기

#### Day 1: 기본 구조 및 ECR
- [ ] **작업 1**: 프로젝트 구조 생성
  - 커밋: `feat: add terraform basic structure and gitignore`
  - 디렉토리 생성: `infra/terraform/prod/`
  - `.gitignore` 작성

- [ ] **작업 2**: ECR 리포지토리 구성
  - 커밋: `feat: add ECR repository configuration`
  - `main.tf`에 provider 설정
  - ECR 리소스 추가
  - `terraform init`, `plan`, `apply` 실행
  - **학습 포인트**: Provider, Resource, `terraform init`

#### Day 2: IAM, ECS 구성
- [ ] **작업 3**: IAM 역할 추가
  - 커밋: `feat: add IAM roles for ECS tasks`
  - Task Execution Role, Task Role 추가
  - **학습 포인트**: IAM Policy Document, Trust Policy

- [ ] **작업 4**: ECS 클러스터 및 Task Definition
  - 커밋: `feat: add ECS cluster and task definition`
  - ECS 클러스터, CloudWatch Logs 추가
  - Task Definition 작성
  - **학습 포인트**: ECS 개념, jsonencode

- [ ] **작업 5**: ECS 서비스 및 ALB 연동
  - 커밋: `feat: add ECS service with ALB integration`
  - Data Source로 기존 VPC/ALB 참조
  - ECS 서비스 생성
  - **학습 포인트**: Data Source vs Resource, depends_on

- [ ] **작업 6**: 변수화 및 출력
  - 커밋: `feat: add variables and outputs`
  - `variables.tf`, `terraform.tfvars`, `outputs.tf` 분리
  - **학습 포인트**: 변수 활용, 출력값

- [ ] **작업 7**: 문서화
  - 커밋: `docs: add Phase 1 README and usage guide`

**학습 체크리스트**:
- [ ] `terraform init`, `plan`, `apply`, `destroy` 이해
- [ ] Resource vs Data Source 차이점 이해
- [ ] 변수와 출력값 활용법 이해
- [ ] State 파일의 역할 이해

---

### Phase 2: 모듈화 (Day 3-4)

**목표**: 코드 재사용성 향상

#### Day 3: 모듈 분리 시작
- [ ] **작업 1**: ECR 모듈 추출
  - 커밋: `refactor: extract ECR into module`
  - `modules/ecr/` 생성
  - **학습 포인트**: 모듈 구조, 입력/출력

- [ ] **작업 2**: IAM 모듈 추출
  - 커밋: `refactor: extract IAM into module`
  - `modules/iam/` 생성

#### Day 4: 모듈화 완료
- [ ] **작업 3**: Networking 모듈 추출
  - 커밋: `refactor: extract networking data sources into module`
  - `modules/networking/` 생성

- [ ] **작업 4**: ECS 모듈 추출
  - 커밋: `refactor: extract ECS into module`
  - `modules/ecs-fargate/` 생성

- [ ] **작업 5**: 메인 파일 업데이트
  - 커밋: `refactor: update main.tf to use modules`
  - `prod/main.tf`를 모듈 호출로 변경

- [ ] **작업 6**: 모듈 문서화
  - 커밋: `docs: add module documentation`
  - 각 모듈에 README.md 추가

**학습 체크리스트**:
- [ ] 모듈 개념과 필요성 이해
- [ ] 모듈 간 의존성 관리 (outputs → inputs)
- [ ] 변수 전달 방식 이해

---

### Phase 3: S3 Backend + 환경 분리 (Day 5-6)

**목표**: State 원격 관리 및 환경 격리

#### Day 5: S3 Backend 구축
- [ ] **작업 1**: S3 Backend 인프라
  - 커밋: `feat: add S3 backend infrastructure`
  - `global/s3-backend/` 생성
  - S3 버킷, DynamoDB 테이블 생성
  - **학습 포인트**: State의 중요성, Backend 개념

- [ ] **작업 2**: Prod 환경 Backend 마이그레이션
  - 커밋: `feat: migrate prod to S3 backend`
  - `backend.tf` 추가
  - `terraform init -migrate-state`
  - **학습 포인트**: State 마이그레이션

#### Day 6: Dev 환경 추가
- [ ] **작업 3**: Dev 환경 구성
  - 커밋: `feat: add dev environment configuration`
  - `dev/` 디렉토리 복사 및 수정
  - 별도 tfvars로 설정 분리

- [ ] **작업 4**: 문서 업데이트
  - 커밋: `docs: add backend and multi-environment guide`

**학습 체크리스트**:
- [ ] Terraform State의 역할 이해
- [ ] Backend 설정 방법 이해
- [ ] State Locking 개념 이해
- [ ] 환경별 관리 전략 이해

---

### Phase 4: CI/CD 자동화 (Day 7-8)

**목표**: GitHub Actions로 배포 자동화

#### Day 7: Terraform 워크플로우
- [ ] **작업 1**: Terraform Plan 워크플로우
  - 커밋: `feat: add terraform plan workflow for PR`
  - `.github/workflows/terraform-plan.yml`
  - **학습 포인트**: GitHub Actions 기본, PR 워크플로우

- [ ] **작업 2**: Terraform Apply 워크플로우
  - 커밋: `feat: add terraform apply workflow for main`
  - `.github/workflows/terraform-apply.yml`
  - **학습 포인트**: 환경 보호, 승인 프로세스

#### Day 8: Docker 빌드 자동화
- [ ] **작업 3**: Docker 빌드 & 배포 워크플로우
  - 커밋: `feat: add docker build and deploy workflow`
  - `.github/workflows/docker-build.yml`
  - **학습 포인트**: ECR 푸시, ECS 배포

- [ ] **작업 4**: 문서화
  - 커밋: `docs: add CI/CD setup and workflow guide`

**학습 체크리스트**:
- [ ] GitHub Actions 기본 개념
- [ ] AWS OIDC 인증 방식 이해
- [ ] CI/CD 파이프라인 설계

---

### Phase 5: 고도화 (Day 9-10)

**목표**: 프로덕션 수준 기능 추가

#### Day 9: Auto Scaling & 모니터링
- [ ] **작업 1**: Auto Scaling 정책
  - 커밋: `feat: add auto scaling policies`
  - CPU/Memory 기반 스케일링
  - **학습 포인트**: ECS Auto Scaling

- [ ] **작업 2**: CloudWatch 알람
  - 커밋: `feat: add CloudWatch alarms`
  - CPU/Memory 알람 설정

#### Day 10: 보안 & 로깅 강화
- [ ] **작업 3**: 로깅 강화
  - 커밋: `feat: add enhanced logging configuration`
  - Container Insights 활성화

- [ ] **작업 4**: Secrets Manager 연동
  - 커밋: `feat: integrate with Secrets Manager`
  - 민감 정보 Secrets Manager로 이동

- [ ] **작업 5**: 최종 문서화
  - 커밋: `docs: add monitoring and operations guide`
  - Runbook, 모니터링 가이드 작성

**학습 체크리스트**:
- [ ] ECS Auto Scaling 설정 방법
- [ ] CloudWatch Metrics & Alarms
- [ ] 모니터링 Best Practices
- [ ] 보안 강화 방법

## 🔐 보안 체크리스트

### AWS
- [ ] OIDC Provider 생성 및 설정
- [ ] GitHub Actions용 IAM Role (최소 권한)
- [ ] S3 State 버킷 암호화 활성화
- [ ] S3 State 버킷 버전 관리 활성화
- [ ] S3 State 버킷 Public Access 차단
- [ ] DynamoDB State Lock 테이블 생성

### GitHub
- [ ] Repository Secrets 설정 (최소화)
- [ ] Environment 보호 규칙 설정
- [ ] Branch 보호 규칙 (main)
- [ ] Required reviewers 설정
- [ ] CODEOWNERS 파일 생성

### Terraform
- [ ] .gitignore에 민감 파일 추가
- [ ] Provider 버전 고정
- [ ] 변수 Validation 추가
- [ ] 민감 정보 Secrets Manager 사용
- [ ] State 파일 암호화

## 🎯 성공 지표

### 기술적 지표
- [ ] Terraform state S3에 안전하게 저장
- [ ] PR마다 자동 `terraform plan` 실행
- [ ] Main 브랜치 merge 시 자동 배포
- [ ] 인프라 변경 이력 Git으로 추적 가능
- [ ] 배포 시간 30% 단축 (목표: ~3분)
- [ ] 수동 개입 0회
- [ ] 롤백 5분 이내 완료

### 운영 지표
- [ ] 인프라 변경 승인 프로세스 자동화
- [ ] 문서화 완료 (90% 이상)
- [ ] 팀원 이해도 80% 이상
- [ ] 장애 발생 시 복구 시간 50% 단축

## 📚 참고 자료

### Terraform
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [Terraform Best Practices](https://www.terraform-best-practices.com/)
- [ECS Terraform Module](https://registry.terraform.io/modules/terraform-aws-modules/ecs/aws/latest)

### GitHub Actions
- [AWS Actions](https://github.com/aws-actions)
- [Configure AWS Credentials](https://github.com/aws-actions/configure-aws-credentials)
- [Setup Terraform](https://github.com/hashicorp/setup-terraform)

### AWS
- [ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/intro.html)
- [IAM OIDC Identity Providers](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)

## 🚀 시작하기

### Phase 1 시작 명령어

```bash
# 1. 디렉토리 생성
mkdir -p infra/terraform/prod
cd infra/terraform/prod

# 2. .gitignore 생성
cat > ../../../.gitignore << 'EOF'
# Terraform
*.tfstate
*.tfstate.*
.terraform/
.terraform.lock.hcl

# 민감 정보
*.tfvars.local
secrets.auto.tfvars
EOF

# 3. main.tf 작성 (위의 Phase 1 코드 예시 참고)
vim main.tf

# 4. variables.tf, terraform.tfvars, outputs.tf 작성

# 5. Terraform 초기화 및 실행
terraform init
terraform plan
terraform apply

# 6. 출력 확인
terraform output
```

### 학습 팁

1. **작은 단위로 커밋**
   - 하나의 리소스 추가 후 바로 커밋
   - 커밋 메시지에 학습한 내용 메모

2. **실험하기**
   - `terraform plan`으로 변경사항 미리 확인
   - `terraform destroy`로 리소스 삭제 후 재생성해보기
   - 변수 값을 바꿔가며 동작 확인

3. **문서 읽기**
   - 각 리소스의 Terraform 문서 읽기
   - AWS 서비스 공식 문서도 함께 참고

4. **에러 이해하기**
   - 에러 메시지를 천천히 읽고 이해하기
   - 에러를 해결한 방법을 문서화

## 📚 학습 자료

### 필수 문서
- [Terraform 공식 튜토리얼](https://learn.hashicorp.com/terraform)
- [AWS Provider 문서](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [ECS 공식 문서](https://docs.aws.amazon.com/ecs/)

### 권장 순서
1. Phase 1: Terraform 기본 개념 익히기
2. Phase 2: 모듈화로 코드 정리하기
3. Phase 3: State 관리의 중요성 이해하기
4. Phase 4: CI/CD로 자동화하기
5. Phase 5: 프로덕션 수준으로 개선하기

## 💡 자주 묻는 질문

### Q1: Phase를 건너뛰어도 되나요?
**A**: 권장하지 않습니다. 각 Phase는 이전 Phase의 학습 내용을 기반으로 합니다. 순차적으로 진행하며 개념을 확실히 이해하는 것이 중요합니다.

### Q2: 실수로 리소스를 삭제했어요
**A**: 괜찮습니다! 학습 과정에서 실수는 자연스럽습니다. `terraform apply`로 다시 생성하거나, Git에서 이전 버전으로 돌아가세요.

### Q3: 비용이 얼마나 드나요?
**A**:
- ECS Fargate (2 vCPU, 8GB): 시간당 ~$0.15
- ECR 스토리지: 월 GB당 $0.10
- ALB: 시간당 ~$0.025
- 학습용으로는 하루 사용 후 `terraform destroy`하면 $5 미만

### Q4: 에러가 계속 발생해요
**A**:
1. 에러 메시지를 천천히 읽어보세요
2. `terraform validate`로 문법 확인
3. `terraform fmt`로 형식 정리
4. AWS Console에서 리소스 상태 확인

## 🎓 학습 성과 체크리스트

### 기본 (Phase 1-2 완료 후)
- [ ] Terraform 기본 명령어 (`init`, `plan`, `apply`, `destroy`) 이해
- [ ] Resource와 Data Source 차이 이해
- [ ] 변수와 출력값 활용 가능
- [ ] 모듈 개념 이해 및 작성 가능

### 중급 (Phase 3-4 완료 후)
- [ ] Terraform State의 중요성 이해
- [ ] S3 Backend 설정 및 State Locking 이해
- [ ] 환경별 설정 분리 가능
- [ ] GitHub Actions로 CI/CD 파이프라인 구축

### 고급 (Phase 5 완료 후)
- [ ] Auto Scaling 설정 가능
- [ ] CloudWatch 모니터링 및 알람 설정
- [ ] 보안 Best Practices 적용
- [ ] 프로덕션 수준의 인프라 코드 작성 가능

---

**작성일**: 2025-12-01
**버전**: 2.0 (학습 중심 개정판)
**목적**: IaC 학습 및 실무 적용
