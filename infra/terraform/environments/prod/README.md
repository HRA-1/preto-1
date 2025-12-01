# Production Environment - Preto Streamlit App

## 개요

이 디렉토리는 Preto Streamlit App의 **프로덕션 환경** 인프라를 관리합니다.

모듈 기반 구조를 사용하여 ECR, IAM, ECS, Network 리소스를 조합합니다.

## 빠른 시작

```bash
# 1. 이 디렉토리로 이동
cd infra/terraform/environments/prod

# 2. Terraform 초기화 (모듈 다운로드)
terraform init

# 3. 실행 계획 확인
terraform plan

# 4. 인프라 배포
terraform apply

# 5. 출력값 확인
terraform output
```

## 파일 구조

```
prod/
├── main.tf          # 모듈 조합 및 리소스 정의
├── variables.tf     # 환경 변수
├── outputs.tf       # 환경 출력값
└── README.md        # 이 문서
```

## 사용 중인 모듈

| 모듈 | 용도 | 소스 |
|------|------|------|
| `network` | 기존 VPC/ALB 참조 | `../../modules/network` |
| `iam` | ECS Task IAM 역할 | `../../modules/iam` |
| `ecr` | Docker 이미지 저장소 | `../../modules/ecr` |
| `ecs` | ECS 클러스터/서비스 | `../../modules/ecs` |

## 주요 변수

| 변수명 | 설명 | 기본값 | 재정의 방법 |
|--------|------|--------|------------|
| `aws_region` | AWS 리전 | `ap-northeast-2` | terraform.tfvars |
| `ecs_cpu` | ECS Task CPU | `2048` | terraform.tfvars |
| `ecs_memory` | ECS Task 메모리 | `8192` | terraform.tfvars |
| `ecs_desired_count` | 태스크 수 | `1` | terraform.tfvars |
| `ecr_lifecycle_count` | 보존 이미지 수 | `2` | terraform.tfvars |

전체 변수 목록은 `variables.tf` 참조

## 변수 재정의

프로덕션 환경에 맞게 변수를 재정의하려면 `terraform.tfvars` 파일 생성:

```hcl
# terraform.tfvars
aws_region        = "ap-northeast-2"
ecs_cpu           = "4096"         # 고성능
ecs_memory        = "16384"        # 16GB
ecs_desired_count = 2              # 고가용성
cpu_architecture  = "ARM64"        # 비용 절감

# 민감 정보는 환경 변수로 관리
# export TF_VAR_db_password="secret"
```

**주의**: `terraform.tfvars`는 민감 정보를 포함할 수 있으므로 `.gitignore`에 추가

## 주요 출력값

배포 후 다음 명령어로 중요 정보 확인:

```bash
# ECR 이미지 푸시 URL
terraform output ecr_repository_url

# 애플리케이션 접속 URL
terraform output alb_dns_name

# ECS 클러스터 정보
terraform output ecs_cluster_name
terraform output ecs_service_name

# CloudWatch Logs
terraform output log_group_name
```

## 배포 워크플로우

### 초기 배포

```bash
# 1. 설정 확인
terraform plan

# 2. 승인 후 배포
terraform apply

# 3. ECR에 이미지 푸시 (별도 작업)
aws ecr get-login-password --region ap-northeast-2 | \
  docker login --username AWS --password-stdin \
  $(terraform output -raw ecr_repository_url)

docker tag my-app:latest $(terraform output -raw ecr_repository_url):latest
docker push $(terraform output -raw ecr_repository_url):latest

# 4. 배포 확인
terraform output
```

### 설정 변경 (예: CPU/Memory 증가)

```bash
# 1. variables.tf 또는 terraform.tfvars 수정
# ecs_cpu = "4096"
# ecs_memory = "16384"

# 2. 변경 사항 확인
terraform plan

# 3. 적용
terraform apply

# 4. ECS 서비스가 자동으로 새 Task Definition으로 롤링 업데이트
```

### 애플리케이션 업데이트

```bash
# 1. 새 이미지 빌드 및 ECR 푸시
docker build -t my-app:v2 .
docker tag my-app:v2 $(terraform output -raw ecr_repository_url):latest
docker push $(terraform output -raw ecr_repository_url):latest

# 2. ECS 서비스 강제 재배포 (새 이미지 사용)
aws ecs update-service \
  --cluster $(terraform output -raw ecs_cluster_name) \
  --service $(terraform output -raw ecs_service_name) \
  --force-new-deployment \
  --region ap-northeast-2

# 3. 배포 상태 확인
aws ecs describe-services \
  --cluster $(terraform output -raw ecs_cluster_name) \
  --services $(terraform output -raw ecs_service_name) \
  --region ap-northeast-2
```

## 모니터링

### CloudWatch Logs 확인

```bash
# 실시간 로그 스트리밍
aws logs tail $(terraform output -raw log_group_name) \
  --follow \
  --region ap-northeast-2

# 에러 로그만 필터링
aws logs tail $(terraform output -raw log_group_name) \
  --follow \
  --filter-pattern "ERROR" \
  --region ap-northeast-2
```

### ECS 서비스 상태

```bash
# 서비스 상태 확인
aws ecs describe-services \
  --cluster $(terraform output -raw ecs_cluster_name) \
  --services $(terraform output -raw ecs_service_name) \
  --region ap-northeast-2 \
  --query 'services[0].[serviceName,status,runningCount,desiredCount]' \
  --output table

# 실행 중인 태스크 목록
aws ecs list-tasks \
  --cluster $(terraform output -raw ecs_cluster_name) \
  --service-name $(terraform output -raw ecs_service_name) \
  --region ap-northeast-2
```

### Target Group 헬스체크

```bash
# Target Group의 헬스 상태 확인
aws elbv2 describe-target-health \
  --target-group-arn <TARGET_GROUP_ARN> \
  --region ap-northeast-2
```

## 문제 해결

### 서비스가 시작되지 않음

1. **CloudWatch Logs 확인**
   ```bash
   aws logs tail $(terraform output -raw log_group_name) --region ap-northeast-2
   ```

2. **Task Definition 검증**
   - ECR 이미지가 존재하는지 확인
   - IAM 역할 권한 확인
   - 리소스 할당(CPU/Memory) 적절한지 확인

3. **네트워크 설정 확인**
   - 보안 그룹 규칙
   - 서브넷 라우팅
   - Target Group 헬스체크 경로

### Plan/Apply 실패

```bash
# 모듈 재초기화
terraform init -upgrade

# State 정리 (주의: 신중하게 사용)
terraform refresh
```

### 이전 버전으로 롤백

```bash
# 이전 Task Definition 리비전 찾기
aws ecs list-task-definitions \
  --family-prefix preto-streamlit-app \
  --region ap-northeast-2

# 특정 리비전으로 롤백
aws ecs update-service \
  --cluster $(terraform output -raw ecs_cluster_name) \
  --service $(terraform output -raw ecs_service_name) \
  --task-definition preto-streamlit-app:N \  # N = 이전 리비전 번호
  --region ap-northeast-2
```

## 리소스 정리

```bash
# 주의: 모든 인프라가 삭제됩니다!
terraform destroy

# 특정 리소스만 삭제
terraform destroy -target=module.ecs
```

## 보안 고려사항

1. **민감 정보 관리**
   - `terraform.tfvars`는 Git에 커밋하지 않음
   - 민감 변수는 환경 변수로 전달: `TF_VAR_*`
   - AWS Secrets Manager 사용 권장 (Phase 3+)

2. **IAM 권한**
   - Task Role은 최소 권한 원칙 적용
   - 필요한 AWS 서비스 접근만 허용

3. **네트워크 보안**
   - 보안 그룹 규칙 최소화
   - 필요한 포트만 개방
   - HTTPS 사용 (ALB에서 SSL 종료)

## 비용 최적화

1. **ARM64 아키텍처**: x86 대비 ~20% 저렴
2. **ECR Lifecycle 정책**: 불필요한 이미지 자동 삭제
3. **Auto Scaling**: 트래픽에 따라 자동 조정 (Phase 3+)
4. **CloudWatch Logs**: 14일 보존 기간으로 비용 절감

## 다음 단계

1. **Auto Scaling 설정**: CPU/Memory 기반 자동 확장
2. **S3 Backend**: State 파일 중앙 관리 (Phase 3)
3. **CI/CD 통합**: GitHub Actions 자동 배포 (Phase 4)
4. **모니터링 강화**: CloudWatch Alarms, Dashboard

## 참고 자료

- [상위 Terraform README](../../README.md)
- [모듈 문서](../../modules/)
- [프로젝트 전체 계획](/infra/PLAN.md)
