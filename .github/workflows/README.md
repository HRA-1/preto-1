# GitHub Actions CI/CD

## 워크플로우 개요

| 워크플로우 | 트리거 | 목적 |
|-----------|--------|------|
| `terraform-plan.yml` | PR (infra 변경) | Plan 결과를 PR 코멘트로 표시 |
| `terraform-apply.yml` | main 푸시 (infra 변경) | 인프라 자동 적용 |
| `docker-build.yml` | main 푸시 (app 변경) | 이미지 빌드 및 ECS 배포 |

## 사전 설정

### 1. AWS OIDC Provider 생성

GitHub Actions에서 AWS 인증을 위한 OIDC Provider 설정:

```bash
# OIDC Provider 생성 (AWS Console 또는 CLI)
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

### 2. IAM Role 생성

GitHub Actions용 IAM Role 생성:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:ORG/REPO:*"
        }
      }
    }
  ]
}
```

필요한 권한:
- `AmazonEC2ContainerRegistryFullAccess`
- `AmazonECS_FullAccess`
- `AmazonS3FullAccess` (Terraform State)
- `IAMFullAccess` (Terraform IAM 리소스)
- `ElasticLoadBalancingFullAccess`
- `CloudWatchLogsFullAccess`

### 3. GitHub Secrets 설정

Repository Settings > Secrets and variables > Actions:

| Secret | 값 |
|--------|-----|
| `AWS_ROLE_ARN` | `arn:aws:iam::ACCOUNT_ID:role/GitHubActionsRole` |

### 4. GitHub Environments 설정 (선택)

Repository Settings > Environments:

- `prod` 환경 생성
- 보호 규칙 설정 (Required reviewers)

## 워크플로우 상세

### terraform-plan.yml

```
PR 생성/업데이트
    ↓
infra/terraform/** 변경 감지
    ↓
dev, prod 환경 병렬 실행
    ↓
terraform fmt → init → validate → plan
    ↓
PR에 Plan 결과 코멘트
```

### terraform-apply.yml

```
main 브랜치 푸시
    ↓
infra/terraform/** 변경 감지
    ↓
prod 환경 승인 대기 (Environment 보호 규칙)
    ↓
terraform init → plan → apply
```

### docker-build.yml

```
main 브랜치 푸시
    ↓
app/** 또는 Dockerfile 변경 감지
    ↓
Docker 이미지 빌드 (ARM64)
    ↓
ECR 푸시 (latest + SHA 태그)
    ↓
ECS 서비스 강제 재배포
    ↓
서비스 안정화 대기
```

## 로컬 테스트

### Terraform 수동 실행

```bash
cd infra/terraform/environments/prod
terraform init
terraform plan
terraform apply
```

### Docker 수동 빌드/푸시

```bash
# ECR 로그인
aws ecr get-login-password --region ap-northeast-2 | \
  docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.ap-northeast-2.amazonaws.com

# 빌드 및 푸시
docker build -t preto-streamlit-app .
docker tag preto-streamlit-app:latest ACCOUNT_ID.dkr.ecr.ap-northeast-2.amazonaws.com/preto-streamlit-app:latest
docker push ACCOUNT_ID.dkr.ecr.ap-northeast-2.amazonaws.com/preto-streamlit-app:latest

# ECS 서비스 업데이트
aws ecs update-service --cluster preto-streamlit-app-cluster --service preto-streamlit-app-service --force-new-deployment
```

## 트러블슈팅

### OIDC 인증 실패

```
Error: Could not assume role with OIDC
```

- Trust Policy의 `sub` 조건 확인 (repo 이름 정확히)
- OIDC Provider thumbprint 확인

### Terraform State Lock

```
Error: Error acquiring the state lock
```

- 다른 작업이 실행 중인지 확인
- S3 `.tflock` 파일 확인

### ECS 배포 실패

```
service preto-streamlit-app-service was unable to place a task
```

- ECR에 이미지가 있는지 확인
- Task Definition CPU/Memory 설정 확인
- 서브넷/보안그룹 설정 확인
