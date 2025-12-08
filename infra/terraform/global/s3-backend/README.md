# Terraform State Backend (S3)

Terraform State를 저장하기 위한 S3 버킷 인프라입니다.

## 특징

- **S3 Native Locking**: Terraform 1.10+의 `use_lockfile = true` 사용
- **DynamoDB 불필요**: 비용 절감 및 관리 포인트 감소
- **버전 관리**: State 히스토리 보존 및 롤백 지원
- **암호화**: AES256 서버 측 암호화
- **Public Access 차단**: 보안 강화

## 사용 방법

### 1. Backend 인프라 생성 (최초 1회)

```bash
cd infra/terraform/global/s3-backend
terraform init
terraform plan
terraform apply
```

### 2. 환경별 Backend 설정

생성된 버킷을 사용하여 각 환경의 `backend.tf` 설정:

```hcl
# environments/prod/backend.tf
terraform {
  backend "s3" {
    bucket       = "preto-terraform-state"
    key          = "prod/terraform.tfstate"
    region       = "ap-northeast-2"
    encrypt      = true
    use_lockfile = true  # S3 Native Locking
  }
}
```

### 3. 기존 Local State 마이그레이션

```bash
cd infra/terraform/environments/prod
terraform init -migrate-state
```

## 주의사항

- 이 인프라는 **Local State**로 관리됩니다 (순환 의존성 방지)
- `prevent_destroy = true`로 실수 삭제 방지
- 버킷 이름은 전역 고유해야 합니다

## 비용

- S3 스토리지: ~$0.01/월 (State 파일 수 KB)
- DynamoDB: **$0** (사용하지 않음)
