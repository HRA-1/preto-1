"""
필터 구조화 설정 파일
4단계 필터 시스템을 위한 모든 상수와 설정을 중앙 집중식으로 관리
"""

from typing import Any
from enum import Enum

# ==============================================================================
# 필터 플레이스홀더 상수
# ==============================================================================

FILTER_PLACEHOLDERS = {
    "level1_default": "개요",
    "level2_overview": "개요",
    "level2_select": "개요",
    "level4_all": "전체",
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
# 그룹명 → 개요 파일명 매핑
# ==============================================================================

GROUP_OVERVIEW_FILES: dict[str, str] = {
    "조직 현황 및 인력 변동": "group_조직현황및인력변동.md",
    "성장 및 경력 개발": "group_성장및경력개발.md",
    "인력 구성 및 역량": "group_인력구성및역량.md",
    "근무 문화 및 워라밸": "group_근무문화및워라밸.md",
}


# ==============================================================================
# Level 3: 구분 - 차원 설정 (type과 column 매핑)
# ==============================================================================

DIMENSION_CONFIG: dict[str, dict[str, Any]] = {
    "개요": {"type": "single", "col": None},  # Show proposal overview
    "전체": {"type": "single", "col": None},
    "부서별": {
        "type": "hierarchical",
        "top": "DIVISION_NAME",
        "sub": "OFFICE_NAME",
    },
    "직무별": {"type": "hierarchical", "top": "JOB_L1_NAME", "sub": "JOB_L2_NAME"},
    "직위직급별": {"type": "single", "col": "POSITION_NAME"},
    "성별": {"type": "single", "col": "GENDER"},
    "연령별": {"type": "single", "col": "AGE_BIN"},
    "경력연차별": {"type": "single", "col": "CAREER_BIN"},
    "연봉구간별": {"type": "single", "col": "SALARY_BIN"},
    "지역별": {"type": "single", "col": "REGION_CATEGORY"},
    "계약별": {"type": "single", "col": "CONT_CATEGORY"},
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


# ==============================================================================
# 제안별 필터 형식 설정 (L3/L4 동적 생성)
# ==============================================================================

PROPOSAL_FILTER_FORMATS: dict[str, str] = {
    # Format A: 전체 차원 옵션 + 부서별/직무별 hierarchical drilldown 지원
    "basic_proposal": "FORMAT_A",
    "proposal_01": "FORMAT_A",
    "proposal_03": "FORMAT_A",
    "proposal_04": "FORMAT_A",
    "proposal_06": "FORMAT_C",
    "proposal_08": "FORMAT_A",
    "proposal_11": "FORMAT_A",
    "proposal_12": "FORMAT_A",
    "proposal_14": "FORMAT_A",
    "proposal_16": "FORMAT_A",
    "proposal_17": "FORMAT_A",
    "proposal_19": "FORMAT_A",
    # Format A-b: "개요" + 부서별~계약별 (전체 제외) + hierarchical drilldown 지원
    "proposal_13": "FORMAT_A-b",
    # Format B: 전체 차원 옵션 but hierarchical drilldown 미지원 (L4 항상 "전체")
    "proposal_07": "FORMAT_B",
    "proposal_18": "FORMAT_B",
    "proposal_20": "FORMAT_B",
    # Format B-b: "개요" + 부서별~계약별 (전체 제외) but hierarchical drilldown 미지원
    "proposal_05": "FORMAT_B-b",
    "proposal_09": "FORMAT_B-b",
    # Format C: L3/L4 모두 "전체"만 표시
    "proposal_02": "FORMAT_C",
    "proposal_10": "FORMAT_C",
    "proposal_15": "FORMAT_C",
}

# 기본 차원 옵션 (플레이스홀더 제외)
BASE_DIMENSION_OPTIONS = [
    "부서별",
    "직무별",
    "직위직급별",
    "성별",
    "연령별",
    "경력연차별",
    "연봉구간별",
    "지역별",
    "계약별",
]


# ==============================================================================
# UI 상태 관리
# ==============================================================================


class ViewState(Enum):
    """
    Main content area의 3가지 UI 상태를 나타냄

    - GROUP_OVERVIEW: 그룹 개요 페이지 (L1=개요, L2=개요)
    - PROPOSAL_SELECTION: 제안 선택 안내 페이지 (L1≠개요, L2=개요)
    - DATA_VISUALIZATION: 실제 데이터 시각화 (유효한 제안 선택됨)
    """

    GROUP_OVERVIEW = "group_overview"
    PROPOSAL_SELECTION = "proposal_selection"
    DATA_VISUALIZATION = "data_visualization"


# ==============================================================================
# 필터 플레이스홀더 체크 함수들
# ==============================================================================


def is_group_placeholder(group: str) -> bool:
    """Level 1 그룹이 플레이스홀더인지 확인"""
    return group == FILTER_PLACEHOLDERS["level1_default"]


def is_proposal_placeholder(proposal: str) -> bool:
    """Level 2 제안이 플레이스홀더인지 확인"""
    return proposal in [
        FILTER_PLACEHOLDERS["level2_overview"],
        FILTER_PLACEHOLDERS["level2_select"],
    ]


def is_drilldown_placeholder(drilldown: str) -> bool:
    """Level 4 하위구분이 플레이스홀더인지 확인"""
    return drilldown in [
        FILTER_PLACEHOLDERS["level4_all"],
        FILTER_PLACEHOLDERS["drilldown_all"],
    ]


# ==============================================================================
# 상태 판별 함수
# ==============================================================================


def get_view_state(selected_group: str, selected_proposal: str) -> ViewState:
    """
    현재 선택된 필터 조합을 기반으로 UI 상태를 결정

    Args:
        selected_group: Level 1 그룹 선택값
        selected_proposal: Level 2 제안 선택값

    Returns:
        ViewState: 현재 UI 상태
    """
    if is_group_placeholder(selected_group) and is_proposal_placeholder(
        selected_proposal
    ):
        return ViewState.GROUP_OVERVIEW
    elif not is_group_placeholder(selected_group) and is_proposal_placeholder(
        selected_proposal
    ):
        return ViewState.PROPOSAL_SELECTION
    else:
        return ViewState.DATA_VISUALIZATION


def should_disable_filters(selected_group: str, selected_proposal: str) -> bool:
    """
    Level 3, 4 필터를 비활성화해야 하는지 판별

    제약 조건:
    - L3, L4는 L1(그룹)과 L2(제안)가 모두 선택되어야 활성화됨
    - L1이 "개요" OR L2가 "개요" → L3, L4 필터 비활성화
    - L1≠"개요" AND L2≠"개요" → L3, L4 필터 활성화

    Args:
        selected_group: Level 1 그룹 선택값
        selected_proposal: Level 2 제안 선택값

    Returns:
        bool: True면 L3, L4 필터 비활성화
    """
    return is_group_placeholder(selected_group) or is_proposal_placeholder(
        selected_proposal
    )


def get_dimension_options_for_proposal(proposal: str) -> list[str]:
    """
    제안(L2)에 따라 L3 차원 필터 옵션을 반환

    Args:
        proposal: 제안 ID (e.g., "proposal_01", "basic_proposal")

    Returns:
        list[str]: L3 차원 옵션 리스트

    Examples:
        - FORMAT_A/B: ["개요", "전체", "부서별", "직무별", ...]
        - FORMAT_A-b/B-b: ["개요", "부서별", "직무별", ...] (전체 제외)
        - FORMAT_C: ["개요", "전체"]
    """
    format_type = PROPOSAL_FILTER_FORMATS.get(proposal, "FORMAT_A")

    if format_type == "FORMAT_C":
        # C형식: L3는 "개요", "전체"만 표시
        return ["개요", "전체"]
    elif format_type in ["FORMAT_A", "FORMAT_B"]:
        # A/B형식: 모든 차원 옵션 표시 ("개요", "전체" 포함)
        return ["개요"] + BASE_DIMENSION_OPTIONS
    else:
        # A-b/B-b형식: "개요" + 모든 차원 옵션 ("전체" 제외)
        return ["개요", "전체"] + BASE_DIMENSION_OPTIONS
