# Preto-1: HR Data Analysis & Visualization

HR 데이터 분석 및 시각화를 위한 Streamlit 기반 대시보드입니다.

## 🚀 주요 기능

- **개발 모드**: 빠른 시작을 위한 경량 데이터 (기본값)
  - 직원 20명, 2024년 7월 이후 데이터
  - 로딩 시간: ~0.5-1초 (프로덕션 대비 25-50배 빠름)

- **프로덕션 모드**: 전체 데이터 분석
  - 직원 1000명, 2020년 이후 데이터
  - 로딩 시간: ~15초

## 요구 사항

- [Docker](https://www.docker.com/get-started)

## 빌드 및 실행

### 1. Docker 이미지 빌드

프로젝트 루트 디렉토리에서 다음 명령어를 실행하여 Docker 이미지를 빌드합니다.

```sh
docker build -t preto-1 .
```

### 2. Docker 컨테이너 실행

#### 🔧 개발 모드 (기본값, 빠른 시작)

**추천**: 개발 및 테스트 시 사용하세요. 데이터 로딩이 10-20배 빠릅니다.

```sh
# 방법 1: 그냥 실행 (자동으로 개발 모드)
docker run --name hra -d -p 8501:8501 -p 8888:8888 -v "$(pwd)":/app preto-1

# 방법 2: 명시적으로 개발 모드 지정
docker run --name hra -d -p 8501:8501 -p 8888:8888 -v "$(pwd)":/app -e ENVIRONMENT=dev preto-1
```

**자동 설정**:
- ✅ Streamlit 앱 (포트 8501)
- ✅ Jupyter Notebook (포트 8888)
- ✅ 빠른 데이터 로딩 (20명, 2024년 7월-현재)

#### 🚀 프로덕션 모드 (전체 데이터)

전체 데이터로 분석이 필요할 때 사용하세요.

```sh
docker run --name hra -d -p 8501:8501 -v "$(pwd)":/app -e ENVIRONMENT=prod preto-1
```

**자동 설정**:
- ✅ Streamlit 앱 (포트 8501)
- ⚠️ Jupyter Notebook 비활성화 (보안)
- ⚠️ 전체 데이터 로딩 (1000명, 2020-현재, 약 15초 소요)

> **윈도우 사용자 참고**:
>
> Windows 환경에서는 `$(pwd)` 대신 다음을 사용하세요:
>
> - **Command Prompt (CMD)**: `%cd%`
> - **PowerShell**: `${pwd}`
>
> 예시:
> ```cmd
> docker run --name hra -d -p 8501:8501 -p 8888:8888 -v "%cd%":/app preto-1
> ```



## 사용 방법

### 웹 인터페이스 접속

-   **Streamlit 앱 (대시보드)**
    -   URL: [http://localhost:8501](http://localhost:8501)
    -   개발 모드/프로덕션 모드 모두 사용 가능

-   **Jupyter Notebook (개발 모드에만 사용 가능)**
    -   URL: [http://localhost:8888](http://localhost:8888)
    -   프로덕션 모드에서는 보안상 비활성화됨

### 로컬 환경에서 직접 실행 (Docker 없이)

#### 개발 모드 (기본값)
```sh
# Python 가상환경 활성화 후
streamlit run src/app.py

# 또는 환경변수 명시
STREAMLIT_DEV_MODE=true streamlit run src/app.py
```

#### 프로덕션 모드
```sh
STREAMLIT_DEV_MODE=false streamlit run src/app.py
```

### 유틸리티 스크립트

-   **Notebook 변환 스크립트 실행**

    `.ipynb` 파일의 변경 사항을 `.py` 스크립트로 변환하려면, 다음 명령어를 실행합니다.

    ```sh
    docker exec hra python convert_notebooks.py
    ```

## 컨테이너 관리

-   **컨테이너 중지:**
    ```sh
    docker stop hra
    ```

-   **컨테이너 시작:**
    ```sh
    docker start hra
    ```

-   **컨테이너 재시작:**
    ```sh
    docker restart hra
    ```

-   **컨테이너 삭제:**
    ```sh
    docker rm hra
    ```

-   **컨테이너 로그 확인:**
    ```sh
    docker logs hra
    ```

-   **컨테이너 내부 접근:**
    ```sh
    docker exec -it hra /bin/bash
    ```

## 📊 성능 비교

| 모드 | 직원 수 | 날짜 범위 | 예상 데이터량 | 로딩 시간 | 사용 사례 |
|------|---------|-----------|--------------|----------|-----------|
| **개발** | 20명 | 2024년 7월-현재 | ~5K 행 | ~0.5-1초 | 개발, 테스트, 빠른 확인 |
| **프로덕션** | 1000명 | 2020-현재 | ~2.2M 행 | ~15초 | 실제 분석, 데모, 배포 |

## 🔍 확인 방법

컨테이너 실행 시 로그에서 현재 모드를 확인할 수 있습니다:

```sh
docker logs hra
```

### 개발 모드 로그 예시
```
🔍 Detected environment: dev
🚀 Starting in DEVELOPMENT mode...
🔧 [DEV MODE] 개발 모드 활성화:
   - 직원 수: 20명
   - 날짜 범위: 2024-07-01 ~ 현재
   - 예상 로딩 속도: 25-50배 향상
📓 Starting Jupyter Notebook on port 8888...
🎯 Starting Streamlit app on port 8501...
```

### 프로덕션 모드 로그 예시
```
🔍 Detected environment: prod
🚀 Starting in PRODUCTION mode...
🔧 STREAMLIT_DEV_MODE=false (1000 employees, 2020-current data)
🎯 Starting Streamlit app on port 8501...
```

## ⚙️ 고급 설정

### 데이터 크기 커스터마이징

개발 모드의 데이터 크기를 조정하려면 `src/services/config/dev_config.py` 파일을 수정하세요:

```python
if DEV_MODE:
    NUM_EMPLOYEES = 20        # 원하는 직원 수로 변경
    DATE_RANGE_START = "2024-07-01"  # 원하는 시작 날짜로 변경
```

### Streamlit 최적화 설정

개발 환경 성능 향상을 위한 설정이 `.streamlit/config.toml`에 포함되어 있습니다:
- 빠른 재실행 (`fastReruns = true`)
- 파일 감지 최적화 (`fileWatcherType = "poll"`)
- 개발자 모드 툴바 활성화

### 환경변수로 직접 제어

```sh
# 컨테이너 실행 시 직접 지정
docker run --name hra -d \
  -p 8501:8501 -p 8888:8888 \
  -e STREAMLIT_DEV_MODE=true \
  -v "$(pwd)":/app \
  preto-1
```

## 📚 추가 문서

- 상세 개발 모드 가이드: [DEV_MODE_GUIDE.md](DEV_MODE_GUIDE.md)

## 🚨 주의사항

1. **개발 모드는 개발/테스트 전용**입니다. 데이터 크기가 작아 일부 통계가 부정확할 수 있습니다.
2. 프로덕션 배포 시 반드시 `ENVIRONMENT=prod`로 설정하세요.
3. 로컬 파일을 볼륨 마운트(`-v`)하면 코드 변경사항이 즉시 반영됩니다.