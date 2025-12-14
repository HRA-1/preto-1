# GitHub Actions CI/CD

## 워크플로우 개요

| 워크플로우 | 트리거 | 목적 |
|-----------|--------|------|
| `terraform-plan.yml` | PR (infra 변경) | Plan 결과를 PR 코멘트로 표시 |
| `terraform-apply.yml` | main 푸시 (infra 변경) | 인프라 자동 적용 |
| `docker-build.yml` | main 푸시 (app 변경) | 이미지 빌드 및 ECS 배포 |

---

## OIDC란?

### 기존 방식의 문제점

```
GitHub Actions에서 AWS 접근하려면?

기존 방식: Access Key 사용
┌─────────────────────────────────────────────────────────┐
│ GitHub Secrets에 저장:                                   │
│   AWS_ACCESS_KEY_ID = AKIA...                           │
│   AWS_SECRET_ACCESS_KEY = wJalrXUtnFEMI...              │
│                                                          │
│ 문제점:                                                  │
│   - 키가 유출되면 AWS 계정 전체 위험                      │
│   - 키 주기적 교체 필요 (관리 부담)                       │
│   - 장기 자격 증명 → 보안 취약                           │
└─────────────────────────────────────────────────────────┘
```

### OIDC (OpenID Connect) 방식

```
OIDC: 임시 자격 증명을 사용한 안전한 인증

┌──────────────┐      1. 토큰 요청       ┌──────────────┐
│   GitHub     │ ──────────────────────▶ │   GitHub     │
│   Actions    │                         │   OIDC       │
│   Workflow   │ ◀────────────────────── │   Provider   │
└──────────────┘      2. JWT 토큰 발급    └──────────────┘
       │
       │ 3. JWT 토큰으로 AWS 역할 요청
       ▼
┌──────────────┐      4. 토큰 검증       ┌──────────────┐
│     AWS      │ ──────────────────────▶ │   GitHub     │
│     IAM      │                         │   OIDC       │
│              │ ◀────────────────────── │   Provider   │
└──────────────┘      5. 검증 완료        └──────────────┘
       │
       │ 6. 임시 자격 증명 발급 (15분~1시간)
       ▼
┌──────────────┐
│   GitHub     │
│   Actions    │ → AWS 리소스 접근 가능!
│   Workflow   │
└──────────────┘

장점:
  - Access Key 저장 불필요 (유출 위험 없음)
  - 임시 자격 증명 (자동 만료)
  - 특정 Repository/Branch만 허용 가능
```

### OIDC JWT 토큰 내용

GitHub Actions가 생성하는 JWT 토큰 예시:

```json
{
  "iss": "https://token.actions.githubusercontent.com",
  "sub": "repo:HRA-1/preto-1:ref:refs/heads/main",
  "aud": "sts.amazonaws.com",
  "ref": "refs/heads/main",
  "repository": "HRA-1/preto-1",
  "actor": "username"
}
```

AWS IAM은 이 토큰의 `sub` 값을 확인하여 어떤 Repository에서 요청했는지 검증합니다.

---

## 설정 단계

### Step 1: AWS OIDC Provider 생성

GitHub을 AWS가 신뢰할 수 있는 ID 제공자로 등록합니다.

```bash
# OIDC Provider 생성
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

**설명**:
- `--url`: GitHub OIDC Provider URL
- `--client-id-list`: AWS STS 서비스
- `--thumbprint-list`: GitHub 인증서 지문 (고정값)

**확인**:
```bash
aws iam list-open-id-connect-providers
# arn:aws:iam::201023212334:oidc-provider/token.actions.githubusercontent.com
```

---

### Step 2: IAM Role 생성

GitHub Actions가 Assume할 수 있는 역할을 생성합니다.

#### 2-1. Trust Policy 작성

```bash
cat > trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::201023212334:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:HRA-1/preto-1:*"
        }
      }
    }
  ]
}
EOF
```

**Trust Policy 해석**:

```
"Principal": { "Federated": "...oidc-provider/token.actions.githubusercontent.com" }
  → GitHub OIDC Provider를 신뢰함

"Action": "sts:AssumeRoleWithWebIdentity"
  → OIDC 토큰으로 역할 수임 허용

"Condition": {
  "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
    → 대상이 AWS STS인 토큰만 허용

  "token.actions.githubusercontent.com:sub": "repo:HRA-1/preto-1:*"
    → HRA-1/preto-1 리포지토리에서만 허용
    → 다른 리포지토리는 이 역할 사용 불가!
}
```

**보안 강화 옵션**:

```json
// 특정 브랜치만 허용
"token.actions.githubusercontent.com:sub": "repo:HRA-1/preto-1:ref:refs/heads/main"

// 특정 환경만 허용
"token.actions.githubusercontent.com:sub": "repo:HRA-1/preto-1:environment:prod"
```

#### 2-2. IAM Role 생성

```bash
aws iam create-role \
  --role-name GitHubActionsRole \
  --assume-role-policy-document file://trust-policy.json \
  --description "GitHub Actions OIDC role for preto-1"
```

#### 2-3. 권한 정책 연결

```bash
# ECR 접근 (Docker 이미지 push/pull)
aws iam attach-role-policy --role-name GitHubActionsRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryFullAccess

# ECS 관리 (서비스 배포)
aws iam attach-role-policy --role-name GitHubActionsRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonECS_FullAccess

# S3 접근 (Terraform State)
aws iam attach-role-policy --role-name GitHubActionsRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

# IAM 관리 (Terraform IAM 리소스)
aws iam attach-role-policy --role-name GitHubActionsRole \
  --policy-arn arn:aws:iam::aws:policy/IAMFullAccess

# ALB 관리 (Terraform Network)
aws iam attach-role-policy --role-name GitHubActionsRole \
  --policy-arn arn:aws:iam::aws:policy/ElasticLoadBalancingFullAccess

# CloudWatch Logs
aws iam attach-role-policy --role-name GitHubActionsRole \
  --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess

# EC2 (VPC, Security Group 등)
aws iam attach-role-policy --role-name GitHubActionsRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2FullAccess
```

#### 2-4. Role ARN 확인

```bash
aws iam get-role --role-name GitHubActionsRole --query 'Role.Arn' --output text
# 출력: arn:aws:iam::201023212334:role/GitHubActionsRole
```

---

### Step 3: GitHub Secret 설정

1. GitHub Repository 페이지 접속
2. **Settings** → **Secrets and variables** → **Actions**
3. **New repository secret** 클릭
4. 입력:
   - Name: `AWS_ROLE_ARN`
   - Value: `arn:aws:iam::201023212334:role/GitHubActionsRole`

---

### Step 4: GitHub Environment 설정 (선택)

프로덕션 배포 시 승인 프로세스를 추가하려면:

1. **Settings** → **Environments** → **New environment**
2. Name: `prod`
3. **Environment protection rules**:
   - ✅ Required reviewers → 승인자 추가
   - ✅ Wait timer → 배포 전 대기 시간

---

## 워크플로우에서 OIDC 사용

```yaml
# 워크플로우 파일
permissions:
  id-token: write   # ← OIDC 토큰 발급 권한 필수!
  contents: read

jobs:
  deploy:
    steps:
      - name: Configure AWS Credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}  # ← IAM Role ARN
          aws-region: ap-northeast-2

      # 이후 AWS CLI/SDK 사용 가능
      - run: aws s3 ls
```

**동작 순서**:
1. GitHub Actions가 OIDC 토큰 생성
2. `configure-aws-credentials` 액션이 토큰으로 AWS STS 호출
3. AWS가 토큰 검증 후 임시 자격 증명 발급
4. 이후 step에서 AWS 리소스 접근 가능

---

## 설정 검증

### OIDC Provider 확인

```bash
aws iam list-open-id-connect-providers
```

### IAM Role 확인

```bash
# Role 존재 확인
aws iam get-role --role-name GitHubActionsRole

# 연결된 정책 확인
aws iam list-attached-role-policies --role-name GitHubActionsRole
```

### 수동 테스트 (로컬에서는 불가)

OIDC 인증은 GitHub Actions 환경에서만 동작합니다.
테스트하려면 PR을 생성하거나 워크플로우를 수동 실행하세요.

---

## 트러블슈팅

### OIDC 인증 실패

```
Error: Could not assume role with OIDC: Not authorized to perform sts:AssumeRoleWithWebIdentity
```

**확인사항**:
1. Trust Policy의 `sub` 조건이 정확한지 (org/repo 이름)
2. OIDC Provider가 생성되어 있는지
3. 워크플로우에 `permissions.id-token: write` 있는지

### Terraform State Lock

```
Error: Error acquiring the state lock
```

- S3 버킷의 `.tflock` 파일 확인
- 다른 terraform 작업이 실행 중인지 확인

### ECS 배포 실패

```
service was unable to place a task
```

- ECR에 이미지 존재하는지 확인
- Task Definition의 CPU/Memory 설정
- 서브넷이 퍼블릭인지, NAT Gateway가 있는지

---

## 참고 자료

- [GitHub OIDC 공식 문서](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [AWS IAM OIDC Provider](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)
- [aws-actions/configure-aws-credentials](https://github.com/aws-actions/configure-aws-credentials)
