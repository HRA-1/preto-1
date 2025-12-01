# Preto Streamlit App - Terraform Infrastructure (Phase 1)

## 개요

이 Terraform 설정은 AWS ECS Fargate에서 Streamlit 애플리케이션을 실행하기 위한 인프라를 관리합니다.

**Phase 1 목표**: 기존 Bash 스크립트 기반 인프라를 Terraform으로 전환하여 IaC(Infrastructure as Code) 기반 관리 시작

## 구성 요소

### 생성되는 리소스

1. **ECR (Elastic Container Registry)**
   - Docker 이미지 저장소
   - 보안 취약점 자동 스캔
   - 최신 2개 이미지만 유지 (비용 절감)

2. **IAM 역할**
   - Task Execution Role: ECS 에이전트가 사용 (ECR pull, CloudWatch Logs 작성)
   - Task Role: 컨테이너 애플리케이션이 사용 (현재 권한 없음, 필요 시 확장)

3. **CloudWatch Logs**
   - 컨테이너 로그 저장
   - 14일 보존 기간

4. **ECS (Elastic Container Service)**
   - Fargate 클러스터
   - Task Definition (ARM64, 2 vCPU, 8GB RAM)
   - Service (Desired count: 1)

5. **기존 인프라 참조** (Data Sources)
   - VPC, 서브넷, 보안 그룹, ALB Target Group
   - 기존 Bash 스크립트로 생성된 리소스 재사용

## 사전 요구사항

### 1. 기존 인프라
다음 리소스들이 이미 생성되어 있어야 합니다 (Bash 스크립트로 생성됨):
- VPC 및 서브넷
- 보안 그룹
- Application Load Balancer
- Target Group

### 2. 도구
- Terraform >= 1.5.0
- AWS CLI
- AWS 자격증명 설정

### 3. ECR 이미지
배포 전에 Docker 이미지가 ECR에 푸시되어 있어야 합니다.

## 사용 방법

### 1. 초기화
```bash
cd infra/terraform/prod
terraform init
```

### 2. 설정 확인
`variables.tf`에서 기본값을 확인하거나, 필요시 재정의:
```bash
# 변수 기본값 확인
cat variables.tf

# 필요시 terraform.tfvars 파일 생성
cat > terraform.tfvars <<EOF
ecs_cpu = "4096"
ecs_memory = "16384"
EOF
```

### 3. 실행 계획 확인
```bash
terraform plan
```

### 4. 인프라 배포
```bash
terraform apply
```

### 5. 출력값 확인
```bash
terraform output

# 특정 값만 확인
terraform output ecr_repository_url
terraform output alb_dns_name
```

## 주요 변수

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `aws_region` | AWS 리전 | `ap-northeast-2` |
| `project_name` | 프로젝트 이름 | `preto` |
| `app_name` | 애플리케이션 이름 | `streamlit-app` |
| `ecs_cpu` | ECS 태스크 CPU | `2048` (2 vCPU) |
| `ecs_memory` | ECS 태스크 메모리 | `8192` (8 GB) |
| `ecs_desired_count` | 실행할 태스크 수 | `1` |
| `container_port` | 컨테이너 포트 | `8501` |

전체 변수 목록은 `variables.tf` 파일 참조

## 주요 출력값

| 출력값 | 설명 |
|--------|------|
| `ecr_repository_url` | Docker 이미지 푸시 대상 URL |
| `ecs_cluster_name` | ECS 클러스터 이름 |
| `ecs_service_name` | ECS 서비스 이름 |
| `alb_dns_name` | 애플리케이션 접속 URL |
| `log_group_name` | CloudWatch Logs 그룹 이름 |

전체 출력값 목록은 `outputs.tf` 파일 참조

## 파일 구조

```
prod/
├── main.tf          # 메인 리소스 정의
├── variables.tf     # 입력 변수 정의
├── outputs.tf       # 출력값 정의
└── README.md        # 이 문서
```

## 학습 포인트

### 1. Data Sources
```hcl
data "aws_vpc" "main" {
  id = var.vpc_id
}
```
- Terraform 외부에서 생성된 리소스 참조
- 기존 인프라와 통합 가능

### 2. Locals
```hcl
locals {
  name_prefix = "${var.project_name}-${var.app_name}"
}
```
- 반복되는 표현식을 변수처럼 재사용
- 리소스 이름 일관성 유지

### 3. Default Tags
```hcl
provider "aws" {
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}
```
- 모든 리소스에 자동으로 태그 적용
- 수동 태그 관리 불필요

### 4. Task Definition
- `awsvpc` 네트워크 모드: Fargate 필수, 각 태스크가 독립 ENI
- ARM64 아키텍처: x86 대비 약 20% 비용 절감
- `awslogs` 드라이버: CloudWatch Logs 자동 연동

## 배포 후 확인

### 1. ECS 서비스 상태
```bash
aws ecs describe-services \
  --cluster preto-streamlit-app-cluster \
  --services preto-streamlit-app-service \
  --region ap-northeast-2
```

### 2. 실행 중인 태스크
```bash
aws ecs list-tasks \
  --cluster preto-streamlit-app-cluster \
  --service-name preto-streamlit-app-service \
  --region ap-northeast-2
```

### 3. CloudWatch Logs
```bash
# 실시간 로그 확인
aws logs tail /ecs/preto-streamlit-app --follow --region ap-northeast-2
```

### 4. 애플리케이션 접속
```bash
# ALB DNS 확인
terraform output alb_dns_name

# 브라우저에서 http://<ALB_DNS> 로 접속
```

## 주의사항

### 1. 기존 인프라 의존성
현재 VPC, ALB 등은 Bash 스크립트로 관리됩니다. 이들을 삭제하면 이 Terraform 설정이 작동하지 않습니다.

**해결 방법 (Phase 2)**: 모든 인프라를 Terraform으로 이관

### 2. State 파일 관리
현재 State 파일이 로컬에 저장됩니다. 팀 협업 시 충돌 가능성이 있습니다.

**해결 방법 (Phase 3)**: S3 Backend 설정으로 State 파일 중앙 관리

### 3. ECR 이미지 태그
현재 `:latest` 태그를 사용합니다. 프로덕션에서는 명시적 태그 사용을 권장합니다.

**개선 방법**: `var.image_tag` 변수 추가 및 CI/CD에서 빌드 번호 전달

## 다음 단계 (Phase 2)

1. **모듈화**: 리소스를 논리적 단위로 분리 (network, ecs, iam 등)
2. **환경 분리**: dev, staging, prod 환경별 설정
3. **네트워크 인프라**: VPC, ALB 등도 Terraform으로 관리
4. **입력 검증**: 변수 validation 추가

자세한 내용은 `/infra/PLAN.md` 참조

## 리소스 정리

```bash
# 주의: 모든 리소스가 삭제됩니다
terraform destroy
```

## 문제 해결

### Plan/Apply 실패 시
1. AWS 자격증명 확인: `aws sts get-caller-identity`
2. 기존 인프라 존재 확인: `variables.tf`의 ID들이 유효한지 확인
3. Terraform 버전 확인: `terraform version`

### 서비스가 시작되지 않을 때
1. CloudWatch Logs 확인
2. Task Definition의 이미지 URI 확인
3. 보안 그룹 규칙 확인
4. IAM 역할 권한 확인

## 참고 자료

- [Terraform AWS Provider 문서](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS ECS Fargate 문서](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html)
- [프로젝트 마이그레이션 계획](/infra/PLAN.md)
