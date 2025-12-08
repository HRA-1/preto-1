# Dev Environment

개발 환경 Terraform 설정입니다.

## Prod와의 차이점

| 항목 | Dev | Prod |
|------|-----|------|
| CPU | 512 (0.5 vCPU) | 2048 (2 vCPU) |
| Memory | 1024 MB | 8192 MB |
| ECR 이미지 보존 | 10개 | 2개 |
| State 경로 | `dev/terraform.tfstate` | `prod/terraform.tfstate` |

## 사용 방법

```bash
cd infra/terraform/environments/dev

# 초기화 (S3 Backend 연결)
terraform init

# 변경사항 확인
terraform plan

# 적용
terraform apply
```

## 주의사항

- Dev 환경은 **학습/테스트 용도**입니다
- 현재 Prod와 동일한 VPC/ALB를 참조합니다 (실제 운영 시 분리 권장)
- 비용 절감을 위해 작은 리소스 사용
