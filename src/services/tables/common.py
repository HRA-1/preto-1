"""
테이블 생성을 위한 공통 상수 및 유틸리티

모든 테이블 모듈에서 공통으로 사용하는 상수를 중앙 집중식으로 관리
개발 모드 설정에 따라 데이터 생성 크기를 자동으로 조정
"""

from datetime import datetime
from services.config.dev_config import (
    NUM_EMPLOYEES,
    DATE_RANGE_START,
    DATE_RANGE_END,
    DEV_MODE,
)

# ==============================================================================
# 데이터 생성 공통 상수
# ==============================================================================

# 직원 수 (개발 모드: 50명, 프로덕션: 1000명)
TOTAL_EMPLOYEES = NUM_EMPLOYEES

# 날짜 범위 (개발 모드: 2024-현재, 프로덕션: 2020-현재)
START_DATE = datetime.strptime(DATE_RANGE_START, "%Y-%m-%d").date()
END_DATE = datetime.strptime(DATE_RANGE_END, "%Y-%m-%d").date()

# 기타 공통 설정
RANDOM_SEED = 42  # 재현 가능한 랜덤 데이터 생성용

# ==============================================================================
# 유틸리티 함수
# ==============================================================================


def get_date_range():
    """데이터 생성에 사용할 날짜 범위 반환"""
    return START_DATE, END_DATE


def get_employee_count():
    """생성할 직원 수 반환"""
    return TOTAL_EMPLOYEES


def is_dev_mode():
    """개발 모드 여부 반환"""
    return DEV_MODE
