import streamlit as st
import streamlit_analytics2 as streamlit_analytics
import os
import importlib.util
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from services.config.filters_config import (
    FILTER_PLACEHOLDERS,
    PROPOSAL_TITLES,
    PROPOSAL_GROUPS,
    DIMENSION_CONFIG,
    PROPOSAL_DATA_FUNCTION_NAMES,
    GROUP_OVERVIEW_FILES,
    PROPOSAL_FILTER_FORMATS,
    ViewState,
    get_view_state,
    is_drilldown_placeholder,
    is_proposal_placeholder,
    should_disable_filters,
    get_dimension_options_for_proposal,
)
from services import data_preparer

# Configure page layout - must be first st command
st.set_page_config(
    page_title="HR Analytics Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "HR Analytics Dashboard",
    },
)

PROPOSAL_VIEWS_DIR = "src/services/proposal_views"
OVERVIEWS_DIR = "src/overviews"
PROPOSAL_OVERVIEWS_DIR = "src/overviews/groups"


def load_markdown_content(filename, group_dir=None):
    """
    개요 마크다운 파일을 로드하여 내용을 반환

    Args:
        filename: 마크다운 파일명 (예: "group_overview.md")
        group_dir: 그룹 디렉토리명 (예: "조직현황및인력변동"), None이면 루트

    Returns:
        str: 마크다운 파일 내용 (파일이 없으면 기본 메시지 반환)
    """
    if group_dir:
        file_path = os.path.join(OVERVIEWS_DIR, "groups", group_dir, filename)
    else:
        file_path = os.path.join(OVERVIEWS_DIR, filename)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        st.warning(f"개요 파일을 찾을 수 없습니다: {filename}")
        return (
            f"# 콘텐츠를 불러올 수 없습니다\n\n`{file_path}` 파일이 존재하지 않습니다."
        )
    except Exception as e:
        st.error(f"파일 로드 중 오류 발생: {e}")
        return f"# 오류\n\n파일을 읽는 중 오류가 발생했습니다."


def get_drilldown_options(
    dimension_ui_name, dimension_config, data_bundle, proposal_name=None
):
    """
    Returns drilldown options based on the selected dimension and proposal format.

    Args:
        dimension_ui_name: Selected L3 dimension (e.g., "부서별")
        dimension_config: DIMENSION_CONFIG dictionary
        data_bundle: Data loaded from data_preparer
        proposal_name: Selected proposal ID (e.g., "proposal_01")

    Returns:
        list[str]: L4 drilldown options
    """
    # If dimension is "개요", return placeholder for drilldown
    if dimension_ui_name == "개요":
        return [FILTER_PLACEHOLDERS["level4_all"]]

    config = dimension_config.get(dimension_ui_name, {})

    # Check proposal format to determine drilldown behavior
    format_type = (
        PROPOSAL_FILTER_FORMATS.get(proposal_name, "FORMAT_A")
        if proposal_name
        else "FORMAT_A"
    )

    # Format B, B-b, and C: Always flat, no hierarchical drilldown
    if format_type in ["FORMAT_B", "FORMAT_B-b", "FORMAT_C"]:
        return [FILTER_PLACEHOLDERS["drilldown_all"]]

    # Format A and A-b: Support hierarchical drilldown for 부서별/직무별
    if config.get("type") == "hierarchical":
        # For hierarchical dimensions, get unique top-level values
        top_col = config.get("top")
        if top_col and data_bundle:
            # Try to get from any available data source in the bundle
            for key, value in data_bundle.items():
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        if (
                            isinstance(sub_value, pd.DataFrame)
                            and top_col in sub_value.columns
                        ):
                            unique_values = sub_value[top_col].dropna().unique()
                            return [FILTER_PLACEHOLDERS["drilldown_all"]] + sorted(
                                unique_values.tolist()
                            )
                elif isinstance(value, pd.DataFrame) and top_col in value.columns:
                    unique_values = value[top_col].dropna().unique()
                    return [FILTER_PLACEHOLDERS["drilldown_all"]] + sorted(
                        unique_values.tolist()
                    )

    return [FILTER_PLACEHOLDERS["drilldown_all"]]


def normalize_filter_values(dimension_ui_name, drilldown_selection):
    """
    플레이스홀더를 실제 값으로 변환

    Args:
        dimension_ui_name: Level 3 구분 선택값
        drilldown_selection: Level 4 하위구분 선택값

    Returns:
        tuple: (정규화된 dimension, 정규화된 drilldown)
    """
    # Dimension 정규화: 이미 유효한 값이므로 그대로 사용
    final_dimension = dimension_ui_name

    # Drilldown 정규화: 플레이스홀더면 "전체"로 변환
    final_drilldown = (
        drilldown_selection
        if not is_drilldown_placeholder(drilldown_selection)
        else FILTER_PLACEHOLDERS["drilldown_all"]
    )

    return final_dimension, final_drilldown


def build_title(proposal_name, dimension_ui_name, drilldown_selection):
    """
    현재 필터 조합을 기반으로 타이틀 문자열 생성

    Args:
        proposal_name: 제안 ID
        dimension_ui_name: Level 3 구분 선택값
        drilldown_selection: Level 4 하위구분 선택값

    Returns:
        str: 생성된 타이틀 문자열
    """
    # 기본 타이틀: 제안 표시명
    proposal_display = PROPOSAL_TITLES.get(proposal_name, proposal_name)
    title = f"{proposal_display}"

    # Dimension이 유효하면 추가 ("개요", "전체" 제외)
    if dimension_ui_name not in ["개요", "전체"]:
        title += f" - {dimension_ui_name}"

    # Drilldown이 유효하면 추가
    if not is_drilldown_placeholder(drilldown_selection):
        title += f" ({drilldown_selection})"

    return title


@st.cache_data
def get_data_bundle_for_proposal(proposal_name: str, dimension_ui_name: str = "전체"):
    """
    Gets the appropriate data bundle for the selected proposal.
    Only loads data when a valid proposal is selected.
    """
    # Don't load data for placeholder selections
    if not proposal_name or proposal_name.startswith("필터"):
        return {"analysis_df": pd.DataFrame(), "order_map": {}}

    # Get data preparation function from config
    function_name = PROPOSAL_DATA_FUNCTION_NAMES.get(proposal_name)
    prepare_func = (
        getattr(data_preparer, function_name, None) if function_name else None
    )
    if prepare_func:
        # Call the preparation function with default global filters
        with st.spinner(f"'{proposal_name}' 데이터를 불러오는 중..."):
            result = prepare_func(
                filter_division="전체",
                filter_job_l1="전체",
                filter_position="전체",
                filter_gender="전체",
                filter_age_bin="전체",
                filter_career_bin="전체",
                filter_salary_bin="전체",
                filter_region="전체",
                filter_contract="전체",
            )
            # Handle different return structures from prepare functions
            if isinstance(result, dict):
                if "data_bundle" in result:
                    # prepare_basic_proposal_data style: {"data_bundle": {...}, "order_map": {...}}
                    data_bundle = result["data_bundle"]
                    data_bundle["order_map"] = result.get("order_map", {})
                    return data_bundle
                elif "cohort_data_bundle" in result:
                    # prepare_proposal_06_data style: {"cohort_data_bundle": {...}, "order_map": {...}}
                    return {
                        "cohort_data_bundle": result["cohort_data_bundle"],
                        "order_map": result.get("order_map", {}),
                    }
                elif "turnover_data" in result:
                    # prepare_proposal_05_data style: {"turnover_data": {...}, "order_map": {...}}
                    return {
                        "turnover_data": result["turnover_data"],
                        "order_map": result.get("order_map", {}),
                    }
                else:
                    # Standard style: {"analysis_df": ..., "order_map": ...} and variations
                    return result
            return result
    else:
        return {"analysis_df": pd.DataFrame(), "order_map": {}}


@st.cache_data
def load_proposal_view(
    proposal_name: str,
    dimension_ui_name: str,
    drilldown_selection: str,
    dimension_config: dict,
    data_bundle: dict,
    order_map: dict,
):
    """
    Dynamically imports and executes the proposal view module.
    Returns a tuple (figure, aggregate_df).
    """
    module_filename = f"{proposal_name}_view.py"
    module_path = os.path.join(PROPOSAL_VIEWS_DIR, module_filename)

    if not os.path.exists(module_path):
        st.warning(f"No view module found: {module_filename}")
        return None, None

    try:
        # Create a unique module name to avoid conflicts
        module_name = (
            f"{proposal_name}_view_{dimension_ui_name}_{drilldown_selection}".replace(
                ".", "_"
            ).replace(" ", "_")
        )
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            st.error(f"Could not create module spec for {module_filename}.")
            return None, None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Call create_figure_and_df with required parameters
        if hasattr(module, "create_figure_and_df"):
            result = module.create_figure_and_df(
                data_bundle=data_bundle,
                dimension_ui_name=dimension_ui_name,
                drilldown_selection=drilldown_selection,
                dimension_config=dimension_config,
                order_map=order_map,
            )
            if isinstance(result, tuple) and len(result) == 2:
                return result
            else:
                st.warning(
                    f"create_figure_and_df in {module_filename} should return a tuple (figure, aggregate_df)"
                )
                return None, None
        else:
            st.warning(f"No create_figure_and_df function found in {module_filename}")
            return None, None

    except Exception as e:
        st.error(f"Error loading view from {module_filename}: {e}")
        import traceback

        st.error(traceback.format_exc())
        return None, None


@st.cache_resource
def load_gif_base64(gif_path):
    """
    GIF 파일을 base64로 인코딩하여 캐시 (앱 레벨, 모든 사용자 공유)

    Args:
        gif_path: GIF 파일 경로

    Returns:
        str: base64 인코딩된 문자열
    """
    import base64
    with open(gif_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def render_group_overview():
    """
    ViewState.GROUP_OVERVIEW 상태의 렌더링
    그룹 개요 페이지 표시 (L1=개요, L2=개요)
    """
    content = load_markdown_content("group_overview.md")
    # Remove the image line from markdown if it exists
    content_without_image = content.replace("![대시보드 사용법](./group_overview.gif)", "")
    st.markdown(content_without_image)

    # GIF 애니메이션 표시 (@st.cache_resource로 앱 레벨 캐싱)
    gif_path = os.path.join(OVERVIEWS_DIR, "group_overview.gif")
    if os.path.exists(gif_path):
        gif_base64 = load_gif_base64(gif_path)
        st.markdown(
            f'<img src="data:image/gif;base64,{gif_base64}" style="width:100%; max-width:100%;">',
            unsafe_allow_html=True
        )


def render_proposal_selection(selected_group):
    """
    ViewState.PROPOSAL_SELECTION 상태의 렌더링
    제안 선택 안내 페이지 표시 (L1≠개요, L2=개요)

    Args:
        selected_group: 선택된 그룹명
    """
    # 그룹 디렉토리명 생성 (공백 제거)
    group_dir = selected_group.replace(" ", "")

    # 그룹별 개요 파일명 가져오기
    filename = GROUP_OVERVIEW_FILES.get(selected_group, "proposal_selection.md")
    content = load_markdown_content(filename, group_dir=group_dir)
    st.markdown(content)


def get_proposal_overview_path(proposal_name, group_name):
    """
    제안 개요 마크다운 파일의 경로를 반환

    Args:
        proposal_name: 제안 ID (e.g., "proposal_01", "basic_proposal")
        group_name: 그룹명 (e.g., "조직 현황 및 인력 변동")

    Returns:
        str: 마크다운 파일의 상대 경로
    """
    # 그룹명에서 공백 제거하여 디렉토리명 생성
    group_dir = group_name.replace(" ", "")
    return os.path.join(PROPOSAL_OVERVIEWS_DIR, group_dir, f"{proposal_name}.md")


def render_proposal_overview(proposal_name, group_name):
    """
    제안 개요 페이지 렌더링 (L3="개요" 선택 시)

    Args:
        proposal_name: 제안 ID
        group_name: 선택된 그룹명
    """
    # 제안 타이틀 표시
    proposal_title = PROPOSAL_TITLES.get(proposal_name, proposal_name)
    st.title(f"{proposal_title}")

    # 개요 파일 경로 가져오기
    overview_path = get_proposal_overview_path(proposal_name, group_name)

    # 마크다운 콘텐츠 로드 및 표시
    try:
        with open(overview_path, "r", encoding="utf-8") as f:
            content = f.read()
        st.markdown(content)
    except FileNotFoundError:
        st.warning(f"개요 파일을 찾을 수 없습니다: {overview_path}")
        st.markdown(
            f"# 콘텐츠를 불러올 수 없습니다\n\n`{overview_path}` 파일이 존재하지 않습니다."
        )
    except Exception as e:
        st.error(f"파일 로드 중 오류 발생: {e}")
        st.markdown(f"# 오류\n\n파일을 읽는 중 오류가 발생했습니다.")


def render_data_visualization(
    proposal_name, dimension_ui_name, drilldown_selection, data_bundle, order_map
):
    """
    ViewState.DATA_VISUALIZATION 상태의 렌더링
    실제 데이터 시각화 표시 (유효한 제안 선택됨)

    Args:
        proposal_name: 제안 ID
        dimension_ui_name: Level 3 구분 선택값 (정규화된 값)
        drilldown_selection: Level 4 하위구분 선택값 (정규화된 값)
        data_bundle: 데이터 번들
        order_map: 정렬 맵
    """
    # 타이틀 생성 및 표시
    title = build_title(proposal_name, dimension_ui_name, drilldown_selection)
    st.title(title)

    # Load and display the proposal view
    fig, aggregate_df = load_proposal_view(
        proposal_name=proposal_name,
        dimension_ui_name=dimension_ui_name,
        drilldown_selection=drilldown_selection,
        dimension_config=DIMENSION_CONFIG,
        data_bundle=data_bundle,
        order_map=order_map,
    )

    # Display the figure
    if fig is not None:
        if isinstance(fig, plt.Figure):
            st.pyplot(fig)
        elif isinstance(fig, go.Figure):
            st.plotly_chart(fig, use_container_width=True)

        # Display aggregate_df if available
        if aggregate_df is not None and not aggregate_df.empty:
            st.subheader("데이터 테이블")
            st.dataframe(aggregate_df, use_container_width=True)
    elif proposal_name == "basic_proposal":
        # basic_proposal_view handles its own display with tabs
        # The view function already displayed content, so we don't need to do anything
        pass
    else:
        st.info("선택하신 조건에 해당하는 데이터가 없거나 시각화를 생성할 수 없습니다.")


def main():
    """
    Main function to run the Streamlit app with 4-filter structure.

    필터 레벨:
    - Level 1 (Sidebar): 그룹 살펴보기
    - Level 2 (Sidebar): 제안 살펴보기
    - Level 3 (Main): 구분
    - Level 4 (Main): 하위구분

    UI 상태:
    - GROUP_OVERVIEW: L1=개요, L2=개요 → 그룹 개요 페이지
    - PROPOSAL_SELECTION: L1≠개요, L2=개요 → 제안 선택 안내 페이지
    - DATA_VISUALIZATION: 유효한 제안 선택 → 실제 데이터 시각화
    """
    with streamlit_analytics.track():
        # ================================================================
        # SIDEBAR - Level 1 & 2 Filters
        # ================================================================

        st.sidebar.title("HR Analytics Graph Collection")
        st.sidebar.markdown("---")

        # LEFT FILTER 1: 그룹 살펴보기 (Group selection)
        selected_group = st.sidebar.selectbox(
            "그룹 살펴보기", options=list(PROPOSAL_GROUPS.keys()), index=0
        )

        # LEFT FILTER 2: 제안 살펴보기 (Proposal selection within the group)
        if selected_group == FILTER_PLACEHOLDERS["level1_default"]:
            # 그룹이 "개요"인 경우: 제안도 "개요"로 고정
            selected_proposal = st.sidebar.selectbox(
                "제안 살펴보기",
                options=[FILTER_PLACEHOLDERS["level2_overview"]],
                index=0,
            )
        elif selected_group and selected_group != FILTER_PLACEHOLDERS["level1_default"]:
            # 유효한 그룹 선택 시: "개요" + 그룹의 제안 리스트
            proposals_in_group = PROPOSAL_GROUPS[selected_group]
            if proposals_in_group:
                proposal_options = [
                    FILTER_PLACEHOLDERS["level2_select"]
                ] + proposals_in_group
                selected_proposal = st.sidebar.selectbox(
                    "제안 살펴보기",
                    options=proposal_options,
                    format_func=lambda x: PROPOSAL_TITLES.get(x, x),
                    index=0,
                )
            else:
                selected_proposal = FILTER_PLACEHOLDERS["level2_select"]
        else:
            st.error("No group selected")
            return

        # ================================================================
        # SIDEBAR - Bottom Links
        # ================================================================
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 소개글 보기")
        st.sidebar.markdown('<a href="https://google.com" target="_blank" style="color: blue; text-decoration: underline;">📄 소개글 보기</a>', 
                            unsafe_allow_html=True)

        st.sidebar.markdown("#### 설문 참여하기")
        st.sidebar.markdown('<a href="https://google.com" target="_blank" style="color: blue; text-decoration: underline;">📝 설문 참여하기</a>', 
                            unsafe_allow_html=True)

        # ================================================================
        # MAIN AREA - Level 3 & 4 Filters
        # ================================================================
        # Determine if filters should be disabled
        # L1(그룹)과 L2(제안)가 모두 선택되어야 L3, L4 필터 활성화
        filters_disabled = should_disable_filters(selected_group, selected_proposal)

        # Custom CSS for filter appearance
        st.markdown(
            """
        <style>
        .top-filters {
            background-color: #f8f9fa;
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1.5rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .stSelectbox {
            margin-bottom: 0.5rem;
        }
        .main-content {
            padding-top: 1rem;
        }
        </style>
        """,
            unsafe_allow_html=True,
        )

        with st.container():
            col1, col2 = st.columns([1, 1])

            with col1:
                # TOP FILTER 3: 구분 (Dimension selection)
                # 제안(L2)에 따라 동적으로 옵션 생성
                if not is_proposal_placeholder(selected_proposal):
                    dimension_options = get_dimension_options_for_proposal(
                        selected_proposal
                    )
                else:
                    # 제안이 선택되지 않은 경우 전체 옵션 표시
                    dimension_options = list(DIMENSION_CONFIG.keys())

                selected_dimension_ui = st.selectbox(
                    "구분",
                    options=dimension_options,
                    index=0,
                    key="dimension_filter",
                    disabled=filters_disabled,  # L1="개요"일 때 비활성화
                )

            with col2:
                # TOP FILTER 4: 하위구분 (Drilldown selection)
                # hierarchical 차원이고 유효한 제안일 때만 데이터 로드
                view_state = get_view_state(selected_group, selected_proposal)
                if (
                    view_state == ViewState.DATA_VISUALIZATION
                    and DIMENSION_CONFIG.get(selected_dimension_ui, {}).get("type")
                    == "hierarchical"
                ):
                    temp_data_bundle = get_data_bundle_for_proposal(
                        selected_proposal, selected_dimension_ui
                    )
                    drilldown_options = get_drilldown_options(
                        selected_dimension_ui,
                        DIMENSION_CONFIG,
                        temp_data_bundle,
                        selected_proposal,
                    )
                else:
                    drilldown_options = get_drilldown_options(
                        selected_dimension_ui,
                        DIMENSION_CONFIG,
                        {},
                        selected_proposal,
                    )

                # L4 비활성화 조건: L1/L2 미선택 OR L3가 "개요"
                drilldown_disabled = filters_disabled or selected_dimension_ui == "개요"

                drilldown_selection = st.selectbox(
                    "하위구분",
                    options=drilldown_options,
                    index=0,
                    key="drilldown_filter",
                    disabled=drilldown_disabled,
                )

        # 필터 비활성화 시 사용자에게 안내 메시지
        if filters_disabled:
            st.caption("💡 그룹과 제안을 선택하면 구분 및 하위구분 필터를 사용할 수 있습니다.")

        # Visual separator
        st.markdown("<hr style='margin: 1.5rem 0;'>", unsafe_allow_html=True)

        # ================================================================
        # MAIN CONTENT - State-based rendering
        # ================================================================
        # Determine current view state
        view_state = get_view_state(selected_group, selected_proposal)

        # Render based on state
        if view_state == ViewState.GROUP_OVERVIEW:
            # 상태 1: 그룹 개요 페이지
            render_group_overview()

        elif view_state == ViewState.PROPOSAL_SELECTION:
            # 상태 2: 제안 선택 안내 페이지
            render_proposal_selection(selected_group)

        elif view_state == ViewState.DATA_VISUALIZATION:
            # 상태 3: 실제 데이터 시각화 또는 제안 개요
            # 필터 값 정규화
            final_dimension, final_drilldown = normalize_filter_values(
                selected_dimension_ui, drilldown_selection
            )

            # L3 필터가 "개요"인 경우: 제안 개요 표시
            if final_dimension == "개요":
                render_proposal_overview(selected_proposal, selected_group)
            else:
                # 데이터 로드 및 렌더링
                with st.spinner("데이터를 불러오는 중..."):
                    data_bundle = get_data_bundle_for_proposal(
                        selected_proposal, final_dimension
                    )
                    order_map = data_bundle.get("order_map", {})

                    render_data_visualization(
                        proposal_name=selected_proposal,
                        dimension_ui_name=final_dimension,
                        drilldown_selection=final_drilldown,
                        data_bundle=data_bundle,
                        order_map=order_map,
                    )


if __name__ == "__main__":
    main()
