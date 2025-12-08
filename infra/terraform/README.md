# Preto Streamlit App - Terraform Infrastructure

## 개요

이 디렉토리는 Preto Streamlit 애플리케이션의 AWS 인프라를 Terraform으로 관리합니다.

**현재 단계**: Phase 3 - S3 Backend + 환경 분리 완료

## 디렉토리 구조

```
terraform/
├── global/               # 글로벌 리소스
│   └── s3-backend/      # Terraform State 저장용 S3 버킷
│
├── modules/              # 재사용 가능한 Terraform 모듈
│   ├── ecr/             # ECR 리포지토리 관리
│   ├── ecs/             # ECS 클러스터, 서비스, Task Definition
│   ├── iam/             # IAM 역할 (Task Execution, Task Role)
│   └── network/         # 네트워크 인프라 참조 (VPC, ALB 등)
│
└── environments/         # 환경별 설정
    ├── dev/             # 개발 환경
    └── prod/            # 프로덕션 환경
```

## 아키텍처 특징

### ✅ 모듈화 구조 (Phase 2)
- 논리적 단위로 모듈 분리 (ECR, IAM, ECS, Network)
- 환경별 디렉토리 구조 (`environments/`)
- 모듈 재사용을 통한 DRY 원칙 적용
- 변수 검증(validation) 추가

**위치**: `modules/`, `environments/prod/`

### ✅ S3 Backend + 환경 분리 (Phase 3)
- Terraform State를 S3에 저장 (`global/s3-backend/`)
- S3 Native Locking (`use_lockfile = true`) - DynamoDB 불필요
- Dev/Prod 환경 분리 (`environments/dev/`, `environments/prod/`)
- Terraform 1.10+ 필수

**State 저장 구조**:
```
s3://preto-terraform-state/
├── dev/terraform.tfstate
└── prod/terraform.tfstate
```

### 🔄 Phase 4: CI/CD 자동화 (예정)
- GitHub Actions 워크플로우
- 자동 배포 파이프라인
- PR 시 terraform plan 자동 실행

## 모듈 설명

### ECR 모듈 (`modules/ecr`)
Docker 이미지 저장소 관리

**입력 변수**:
- `repository_name`: 리포지토리 이름
- `image_tag_mutability`: MUTABLE 또는 IMMUTABLE
- `scan_on_push`: 자동 스캔 여부
- `lifecycle_policy_count`: 보존할 이미지 개수

**출력값**:
- `repository_url`: ECR 리포지토리 URL
- `repository_arn`: ECR 리포지토리 ARN

### IAM 모듈 (`modules/iam`)
ECS Task를 위한 IAM 역할

**입력 변수**:
- `name_prefix`: 역할 이름 접두사

**출력값**:
- `task_execution_role_arn`: Task Execution Role ARN
- `task_role_arn`: Task Role ARN

**생성 리소스**:
- Task Execution Role (ECS 에이전트용)
- Task Role (컨테이너 애플리케이션용)

### ECS 모듈 (`modules/ecs`)
ECS 클러스터 및 서비스 관리

**주요 입력 변수**:
- `cluster_name`, `service_name`, `task_family`
- `container_image`: Docker 이미지 URL
- `cpu`, `memory`: 리소스 할당
- `task_execution_role_arn`, `task_role_arn`: IAM 역할
- `subnets`, `security_groups`: 네트워크 설정
- `target_group_arn`: ALB Target Group

**출력값**:
- `cluster_name`, `service_name`
- `task_definition_arn`, `task_definition_revision`
- `log_group_name`

### Network 모듈 (`modules/network`)
기존 네트워크 인프라 참조

**현재 버전**: Data sources로 기존 인프라 조회
**향후 계획**: VPC, ALB 등 실제 생성 기능 추가 (Phase 3+)

**입력 변수**:
- `vpc_id`, `subnet_ids`, `security_group_id`, `target_group_arn`

**출력값**:
- `vpc_id`, `subnet_ids`, `security_group_id`, `target_group_arn`

## 환경별 사용 방법

### 0. S3 Backend 초기화 (최초 1회)

```bash
# S3 버킷 생성
cd global/s3-backend
terraform init
terraform apply
```

### 1. Production 환경 배포

```bash
cd environments/prod

# S3 Backend로 초기화
terraform init

# 실행 계획 확인
terraform plan

# 인프라 배포
terraform apply

# 출력값 확인
terraform output
```

### 2. Dev 환경 배포

```bash
cd environments/dev

# S3 Backend로 초기화 (별도 State 경로)
terraform init

terraform plan
terraform apply
```

### Local State → S3 마이그레이션 (기존 환경)

```bash
cd environments/prod

# backend.tf 추가 후 마이그레이션
terraform init -migrate-state
# "yes" 입력하여 State 이동 확인
```

### 변수 재정의

환경별로 다른 값을 사용하려면 `terraform.tfvars` 파일 생성:

```hcl
# environments/prod/terraform.tfvars
ecs_cpu    = "4096"
ecs_memory = "16384"
ecs_desired_count = 2
```

## 모듈 사용 예시

### 다른 프로젝트에서 ECR 모듈 재사용

```hcl
module "my_ecr" {
  source = "../../modules/ecr"

  repository_name        = "my-app"
  image_tag_mutability   = "IMMUTABLE"
  lifecycle_policy_count = 5

  tags = {
    Project = "my-project"
  }
}

output "ecr_url" {
  value = module.my_ecr.repository_url
}
```

### Dev 환경 구성

```hcl
# environments/dev/main.tf
module "ecr" {
  source = "../../modules/ecr"

  repository_name        = "preto-streamlit-app-dev"
  lifecycle_policy_count = 5  # Dev는 더 많은 이미지 보존
  tags                   = local.common_tags
}

module "ecs" {
  source = "../../modules/ecs"

  cpu            = "512"   # Dev는 더 작은 리소스
  memory         = "1024"
  desired_count  = 1

  # ... 기타 설정
}
```

## 모듈 간 의존성 관리

모듈은 output → input 방식으로 연결됩니다:

```hcl
# ECR 모듈 생성
module "ecr" {
  source = "../../modules/ecr"
  # ...
}

# IAM 모듈 생성
module "iam" {
  source = "../../modules/iam"
  # ...
}

# ECS 모듈에서 ECR과 IAM 출력값 사용
module "ecs" {
  source = "../../modules/ecs"

  container_image         = "${module.ecr.repository_url}:latest"  # ECR 참조
  task_execution_role_arn = module.iam.task_execution_role_arn      # IAM 참조
  task_role_arn           = module.iam.task_role_arn                # IAM 참조

  # ...
}
```

## 학습 포인트

### 1. 모듈 재사용성
```hcl
# 같은 ECR 모듈로 여러 환경 구성
module "ecr_prod" {
  source              = "../../modules/ecr"
  repository_name     = "app-prod"
  lifecycle_policy_count = 2
}

module "ecr_dev" {
  source              = "../../modules/ecr"
  repository_name     = "app-dev"
  lifecycle_policy_count = 10
}
```

### 2. 변수 검증
```hcl
variable "cpu" {
  type    = string
  default = "2048"

  validation {
    condition     = contains(["256", "512", "1024", "2048", "4096"], var.cpu)
    error_message = "CPU는 유효한 Fargate 값이어야 합니다."
  }
}
```

### 3. 모듈 출력 체이닝
```hcl
# 모듈 A의 출력을 모듈 B의 입력으로 사용
resource_a_output = module.a.output_value  # A → B
resource_b_input  = module.a.output_value  # 의존성 자동 처리
```

## 문제 해결

### 모듈을 찾을 수 없음
```bash
Error: Module not found
```
**해결**: `terraform init` 실행하여 모듈 다운로드

### 순환 의존성 오류
```bash
Error: Cycle: module.a, module.b
```
**해결**: 모듈 간 의존성 재검토, 불필요한 참조 제거

### State 파일 충돌
**문제**: 여러 환경(dev/prod)에서 동일한 리소스 이름 사용
**해결**: 각 환경의 리소스 이름에 환경별 prefix 사용

## 다음 단계

1. **Phase 4**: GitHub Actions CI/CD 파이프라인
2. **Phase 5**: Auto Scaling, CloudWatch 알람, Secrets Manager 연동
3. **Network 모듈 확장**: VPC, ALB 실제 생성 기능 추가

자세한 로드맵은 `/infra/PLAN.md` 참조

## 참고 자료

- [Terraform 모듈 문서](https://developer.hashicorp.com/terraform/language/modules)
- [Terraform S3 Backend](https://developer.hashicorp.com/terraform/language/backend/s3)
- [AWS Provider 문서](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [S3 Backend 설정](global/s3-backend/README.md)
- [환경별 설정 README](environments/prod/README.md)
