"""
필터 구조화 설정 파일
4단계 필터 시스템을 위한 모든 상수와 설정을 중앙 집중식으로 관리
"""

from typing import Any

# ==============================================================================
# 필터 플레이스홀더 상수
# ==============================================================================

FILTER_PLACEHOLDERS = {
    "level1_default": "개요",
    "level2_overview": "필터(개요)",
    "level2_select": "필터(제안 선택)",
    "level3_select": "필터(구분 선택)",
    "level4_all": "필터(전체)",
    "drilldown_all": "전체",
}


# ==============================================================================
# 제안 ID → 제목 매핑 (기존 dict.py에서 이동)
# ==============================================================================

_proposal_list = (
    ["basic_proposal"]
    + [f"proposal_0{i}" for i in range(1, 10)]
    + [f"proposal_{i}" for i in range(10, 21)]
)

_title_list = [
    "기본 현황판: 인원 변동 현황",
    "승진 소요 기간",
    "승진 경로",
    "연령 분포 현황",
    "근속연수 분포 현황",
    "퇴사율 변화 추이",
    "연도별 잔존율",
    "첫 직무별 재직기간",
    "인력 유지 현황",
    "직무 이동률 추이",
    "초봉 관계 분석",
    "초과근무 분포 현황",
    "출근 문화 분석",
    "초과근무 시간 분포",
    "지각률 분포",
    "부서 변경 전후 초과근무 패턴",
    "평균 주말근무 일수",
    "요일별 업무 강도",
    "연차-병가 사용 패턴",
    "퇴사 전 휴가 패턴",
    "부서별 휴가 유형",
]

PROPOSAL_TITLES: dict[str, str] = {
    proposal: title for proposal, title in zip(_proposal_list, _title_list)
}


# ==============================================================================
# Level 1: 그룹 살펴보기 - 그룹명 → 제안 리스트 매핑
# ==============================================================================

PROPOSAL_GROUPS: dict[str, list[str]] = {
    "개요": [],  # Placeholder for initial state
    "조직 현황 및 인력 변동": [
        "basic_proposal",
        "proposal_05",
        "proposal_06",
        "proposal_08",
        "proposal_19",
    ],
    "성장 및 경력 개발": [
        "proposal_01",
        "proposal_02",
        "proposal_09",
        "proposal_15",
    ],
    "인력 구성 및 역량": [
        "proposal_03",
        "proposal_04",
        "proposal_07",
        "proposal_10",
    ],
    "근무 문화 및 워라밸": [
        "proposal_11",
        "proposal_12",
        "proposal_13",
        "proposal_14",
        "proposal_16",
        "proposal_17",
        "proposal_18",
        "proposal_20",
    ],
}


# ==============================================================================
# Level 3: 구분 - 차원 설정 (type과 column 매핑)
# ==============================================================================

DIMENSION_CONFIG: dict[str, dict[str, Any]] = {
    "필터(구분 선택)": {"type": "single", "col": None},  # Placeholder
    "전체": {"type": "single", "col": None},
    "부서별": {
        "type": "hierarchical",
        "top": "DIVISION_NAME",
        "sub": "OFFICE_NAME",
    },
    "직무별": {"type": "hierarchical", "top": "JOB_L1_NAME", "sub": "JOB_L2_NAME"},
    "직위별": {"type": "single", "col": "POSITION_NAME"},
    "성별": {"type": "single", "col": "GENDER"},
    "연령대별": {"type": "single", "col": "AGE_BIN"},
    "경력구간별": {"type": "single", "col": "CAREER_BIN"},
    "연봉구간별": {"type": "single", "col": "SALARY_BIN"},
    "근무지역별": {"type": "single", "col": "REGION_CATEGORY"},
    "계약형태별": {"type": "single", "col": "CONT_CATEGORY"},
}


# ==============================================================================
# 제안 ID → data_preparer 함수명 매핑
# ==============================================================================

# Note: 실제 함수는 data_preparer 모듈에서 import됨
# 이 딕셔너리는 app.py에서 동적으로 함수를 매핑하기 위해 사용

PROPOSAL_DATA_FUNCTION_NAMES: dict[str, str] = {
    "basic_proposal": "prepare_basic_proposal_data",
    "proposal_01": "prepare_proposal_01_data",
    "proposal_02": "prepare_proposal_02_data",
    "proposal_03": "prepare_proposal_03_data",
    "proposal_04": "prepare_proposal_04_data",
    "proposal_05": "prepare_proposal_05_data",
    "proposal_06": "prepare_proposal_06_data",
    "proposal_07": "prepare_proposal_07_data",
    "proposal_08": "prepare_proposal_08_data",
    "proposal_09": "prepare_proposal_09_data",
    "proposal_10": "prepare_proposal_10_data",
    "proposal_11": "prepare_proposal_11_data",
    "proposal_12": "prepare_proposal_12_data",
    "proposal_13": "prepare_proposal_13_data",
    "proposal_14": "prepare_proposal_14_data",
    "proposal_15": "prepare_proposal_15_data",
    "proposal_16": "prepare_proposal_16_data",
    "proposal_17": "prepare_proposal_17_data",
    "proposal_18": "prepare_proposal_18_data",
    "proposal_19": "prepare_proposal_19_data",
    "proposal_20": "prepare_proposal_20_data",
}
