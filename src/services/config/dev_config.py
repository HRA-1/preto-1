"""
개발 모드 설정 파일
환경변수를 통해 개발/프로덕션 모드를 전환하여 데이터 로딩 속도 최적화
"""

import os
from datetime import date

# ==============================================================================
# 개발 모드 플래그
# ==============================================================================

# 환경변수 STREAMLIT_DEV_MODE로 제어
# 사용법:
#   개발 모드: STREAMLIT_DEV_MODE=true streamlit run src/app.py
#   프로덕션: STREAMLIT_DEV_MODE=false streamlit run src/app.py
DEV_MODE = os.getenv("STREAMLIT_DEV_MODE", "true").lower() in ("true", "1", "yes")

# ==============================================================================
# 데이터 생성 설정
# ==============================================================================

if DEV_MODE:
    # 개발 모드: 빠른 로딩을 위해 데이터 크기 축소
    # 환경변수로 오버라이드 가능
    NUM_EMPLOYEES = int(os.getenv("STREAMLIT_NUM_EMPLOYEES", "1000"))
    DATE_RANGE_START = os.getenv("STREAMLIT_DATE_START", "2020-01-01")

    print("🔧 [DEV MODE] 개발 모드 활성화:")
    print(f"   - 직원 수: {NUM_EMPLOYEES}명")
    print(f"   - 날짜 범위: {DATE_RANGE_START} ~ 현재")
    if NUM_EMPLOYEES == 20 and DATE_RANGE_START == "2024-07-01":
        print(f"   - 예상 로딩 속도: 25-50배 향상 (최소 데이터)")
    elif NUM_EMPLOYEES <= 100:
        print(f"   - 예상 로딩 속도: 10-20배 향상 (중간 데이터)")
    else:
        print(f"   - 예상 로딩 속도: 프로덕션 수준 (대용량 데이터)")
else:
    # 프로덕션 모드: 전체 데이터 생성
    NUM_EMPLOYEES = 1000
    DATE_RANGE_START = "2020-01-01"

    print("🚀 [PROD MODE] 프로덕션 모드 활성화:")
    print(f"   - 직원 수: {NUM_EMPLOYEES}명")
    print(f"   - 날짜 범위: {DATE_RANGE_START} ~ 현재")

# 공통 설정
DATE_RANGE_END = date.today().strftime("%Y-%m-%d")

# ==============================================================================
# 추가 최적화 옵션 (향후 확장용)
# ==============================================================================

# 개발 모드에서 특정 테이블 스킵 (현재는 사용 안 함)
SKIP_HEAVY_TABLES = False

# 캐시 설정
ENABLE_DATA_CACHING = True
