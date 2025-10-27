import streamlit as st
import streamlit_analytics2 as streamlit_analytics
import os
import importlib.util
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from services.helpers.dict import name_dictionary
from services import data_preparer

# Configure page layout - must be first st command
st.set_page_config(
    page_title="HR Analytics Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': "HR Analytics Dashboard"
    }
)

PROPOSAL_VIEWS_DIR = "src/services/proposal_views"


def get_proposal_groups():
    """
    Returns proposal groups for the first filter.
    """
    return {
        "필터(그룹 선택)": [],  # Placeholder for initial state
        "인력 현황": ["basic_proposal", "proposal_01", "proposal_02", "proposal_03", "proposal_04"],
        "퇴사/유지": ["proposal_05", "proposal_06", "proposal_07", "proposal_08", "proposal_09"],
        "보상": ["proposal_10"],
        "근태": ["proposal_11", "proposal_12", "proposal_13", "proposal_14", "proposal_15", "proposal_16", "proposal_17"],
        "휴가": ["proposal_18", "proposal_19", "proposal_20"]
    }


def get_dimension_config():
    """
    Returns dimension configuration for the third filter.
    """
    return {
        "필터(구분 선택)": {"type": "single", "col": None},  # Placeholder
        "전체": {"type": "single", "col": None},
        "부서별": {"type": "hierarchical", "top": "DIVISION_NAME", "sub": "OFFICE_NAME"},
        "직무별": {"type": "hierarchical", "top": "JOB_L1_NAME", "sub": "JOB_L2_NAME"},
        "직위별": {"type": "single", "col": "POSITION_NAME"},
        "성별": {"type": "single", "col": "GENDER"},
        "연령대별": {"type": "single", "col": "AGE_BIN"},
        "경력구간별": {"type": "single", "col": "CAREER_BIN"},
        "연봉구간별": {"type": "single", "col": "SALARY_BIN"},
        "근무지역별": {"type": "single", "col": "REGION_CATEGORY"},
        "계약형태별": {"type": "single", "col": "CONT_CATEGORY"}
    }

def get_drilldown_options(dimension_ui_name, dimension_config, data_bundle):
    """
    Returns drilldown options based on the selected dimension.
    """
    # If dimension is the placeholder, return placeholder for drilldown too
    if dimension_ui_name == "필터(구분 선택)":
        return ["필터(전체)"]

    config = dimension_config.get(dimension_ui_name, {})

    if config.get('type') == 'hierarchical':
        # For hierarchical dimensions, get unique top-level values
        top_col = config.get('top')
        if top_col and data_bundle:
            # Try to get from any available data source in the bundle
            for key, value in data_bundle.items():
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        if isinstance(sub_value, pd.DataFrame) and top_col in sub_value.columns:
                            unique_values = sub_value[top_col].dropna().unique()
                            return ['필터(전체)', '전체'] + sorted(unique_values.tolist())
                elif isinstance(value, pd.DataFrame) and top_col in value.columns:
                    unique_values = value[top_col].dropna().unique()
                    return ['필터(전체)', '전체'] + sorted(unique_values.tolist())

    return ['필터(전체)', '전체']


@st.cache_data
def get_data_bundle_for_proposal(proposal_name: str, dimension_ui_name: str = "전체"):
    """
    Gets the appropriate data bundle for the selected proposal.
    Only loads data when a valid proposal is selected.
    """
    # Don't load data for placeholder selections
    if not proposal_name or proposal_name.startswith("필터"):
        return {"analysis_df": pd.DataFrame(), "order_map": {}}

    # Map proposal names to data preparation functions
    prepare_function_map = {
        "basic_proposal": data_preparer.prepare_basic_proposal_data,
        "proposal_01": data_preparer.prepare_proposal_01_data,
        "proposal_02": data_preparer.prepare_proposal_02_data,
        "proposal_03": data_preparer.prepare_proposal_03_data,
        "proposal_04": data_preparer.prepare_proposal_04_data,
        "proposal_05": data_preparer.prepare_proposal_05_data,
        "proposal_06": data_preparer.prepare_proposal_06_data,
        "proposal_07": data_preparer.prepare_proposal_07_data,
        "proposal_08": data_preparer.prepare_proposal_08_data,
        "proposal_09": data_preparer.prepare_proposal_09_data,
        "proposal_10": data_preparer.prepare_proposal_10_data,
        "proposal_11": data_preparer.prepare_proposal_11_data,
        "proposal_12": data_preparer.prepare_proposal_12_data,
        "proposal_13": data_preparer.prepare_proposal_13_data,
        "proposal_14": data_preparer.prepare_proposal_14_data,
        "proposal_15": data_preparer.prepare_proposal_15_data,
        "proposal_16": data_preparer.prepare_proposal_16_data,
        "proposal_17": data_preparer.prepare_proposal_17_data,
        "proposal_18": data_preparer.prepare_proposal_18_data,
        "proposal_19": data_preparer.prepare_proposal_19_data,
        "proposal_20": data_preparer.prepare_proposal_20_data,
    }

    prepare_func = prepare_function_map.get(proposal_name)
    if prepare_func:
        # Call the preparation function with default global filters
        with st.spinner(f"'{proposal_name}' 데이터를 불러오는 중..."):
            result = prepare_func(
                filter_division='전체',
                filter_job_l1='전체',
                filter_position='전체',
                filter_gender='전체',
                filter_age_bin='전체',
                filter_career_bin='전체',
                filter_salary_bin='전체',
                filter_region='전체',
                filter_contract='전체'
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
                        "order_map": result.get("order_map", {})
                    }
                elif "turnover_data" in result:
                    # prepare_proposal_05_data style: {"turnover_data": {...}, "order_map": {...}}
                    return {
                        "turnover_data": result["turnover_data"],
                        "order_map": result.get("order_map", {})
                    }
                else:
                    # Standard style: {"analysis_df": ..., "order_map": ...} and variations
                    return result
            return result
    else:
        return {"analysis_df": pd.DataFrame(), "order_map": {}}


@st.cache_data
def load_proposal_view(proposal_name: str, dimension_ui_name: str, drilldown_selection: str, dimension_config: dict, data_bundle: dict, order_map: dict):
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
        module_name = f"{proposal_name}_view_{dimension_ui_name}_{drilldown_selection}".replace(".", "_").replace(" ", "_")
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
                order_map=order_map
            )
            if isinstance(result, tuple) and len(result) == 2:
                return result
            else:
                st.warning(f"create_figure_and_df in {module_filename} should return a tuple (figure, aggregate_df)")
                return None, None
        else:
            st.warning(f"No create_figure_and_df function found in {module_filename}")
            return None, None

    except Exception as e:
        st.error(f"Error loading view from {module_filename}: {e}")
        import traceback
        st.error(traceback.format_exc())
        return None, None


def main():
    """
    Main function to run the Streamlit app with 4-filter structure.
    """
    with streamlit_analytics.track():
        # SIDEBAR - LEFT FILTERS
        st.sidebar.title("HR Analytics\nGraph Collection")
        st.sidebar.markdown(
            """
            더 이상 '감'과 '경험'에만 의존하는 HR의 시대는 지났습니다.\n
            조직의 숨겨진 리스크와 기회를 객관적 지표로 증명하고 선제적으로 인재관리를 시작하세요.
            """
        )
        st.sidebar.markdown("---")  # Separator line

        # Get configuration
        proposal_groups = get_proposal_groups()
        dimension_config = get_dimension_config()

        # LEFT FILTER 1: 그룹 살펴보기 (Group selection)
        selected_group = st.sidebar.selectbox(
            "그룹 살펴보기",
            options=list(proposal_groups.keys()),
            index=0
        )

        # LEFT FILTER 2: 제안 살펴보기 (Proposal selection within the group)
        if selected_group == "필터(그룹 선택)":
            # Show placeholder for proposal selection
            selected_proposal = st.sidebar.selectbox(
                "제안 살펴보기",
                options=["필터(개요)"],
                index=0
            )
        elif selected_group and selected_group != "필터(그룹 선택)":
            proposals_in_group = proposal_groups[selected_group]
            if proposals_in_group:
                proposal_options = ["필터(제안 선택)"] + proposals_in_group
                selected_proposal = st.sidebar.selectbox(
                    "제안 살펴보기",
                    options=proposal_options,
                    format_func=lambda x: x if x.startswith("필터") else name_dictionary.get(x, x),
                    index=0
                )
            else:
                selected_proposal = "필터(제안 선택)"
        else:
            st.error("No group selected")
            return

        # MAIN AREA - TOP FILTERS
        # Add custom CSS for better filter appearance
        st.markdown("""
        <style>
        /* Style for top filter area */
        .top-filters {
            background-color: #f8f9fa;
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1.5rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        /* Reduce padding for selectbox in columns */
        .stSelectbox {
            margin-bottom: 0.5rem;
        }
        /* Style the main content area */
        .main-content {
            padding-top: 1rem;
        }
        </style>
        """, unsafe_allow_html=True)

        # Create container for top filters
        with st.container():
            col1, col2 = st.columns([1, 1])

            with col1:
                # TOP FILTER 3: 구분 (Dimension selection)
                dimension_options = list(dimension_config.keys())
                selected_dimension_ui = st.selectbox(
                    "구분",
                    options=dimension_options,
                    index=0,
                    key="dimension_filter"
                )

            with col2:
                # TOP FILTER 4: 하위구분 (Drilldown selection)
                # Only get data bundle when necessary for drilldown options
                if selected_proposal and not selected_proposal.startswith("필터") and \
                   selected_dimension_ui and not selected_dimension_ui.startswith("필터") and \
                   dimension_config.get(selected_dimension_ui, {}).get('type') == 'hierarchical':
                    # Only load data for hierarchical dimensions that need drilldown options
                    temp_data_bundle = get_data_bundle_for_proposal(selected_proposal, selected_dimension_ui)
                    drilldown_options = get_drilldown_options(selected_dimension_ui, dimension_config, temp_data_bundle)
                else:
                    drilldown_options = get_drilldown_options(selected_dimension_ui, dimension_config, {})

                drilldown_selection = st.selectbox(
                    "하위구분",
                    options=drilldown_options,
                    index=0,
                    key="drilldown_filter"
                )

        # Visual separator between filters and content
        st.markdown("<hr style='margin: 1.5rem 0;'>", unsafe_allow_html=True)

        # Main content area
        if selected_proposal and selected_dimension_ui:
            # Check different states and display appropriate content
            if selected_group == "필터(그룹 선택)" and selected_proposal == "필터(개요)":
                # Initial state - show overview
                st.title("해당 그룹에 대한 설명")
                st.markdown("""
                ex)

                ## 그룹 1: 조직 현황 및 인력 변동

                - 이 그룹은 조직의 가장 기본적인 건강 상태(Health Check)를 진단합니다. "얼마나 많은 인력이, 얼마나 잘 유지되고 있는가?"라는 질문에 답하며, 인력의 유입(Flow-in)과 유출(Flow-out)을 집중적으로 추적합니다.
                - 포함 그래프
                    - 기본 인원 변동 현황 (전체 현황)
                    - 연간 퇴사율 (핵심 유출 지표)
                    - 입사 연도별 잔존율 (시점별 유출 지표)
                    - 직무별 인력 유지 현황 (직무별 유출 지표)
                    - 퇴사 예측 선행 지표 (유출 선행 지표)
                """)
            elif selected_group != "필터(그룹 선택)" and selected_proposal == "필터(제안 선택)":
                # Group selected but no proposal selected
                st.title("해당 제안에 대한 설명")
                st.markdown(f"""
                기존 내용 유지
                단, '그래프 1: Division/Office별 성장 속도 비교'와 같은 제목은 삭제
                글자 수도 줄일 수 있다면 줄이기
                글씨 크기는 이전 페이지 포함해서 키울 수 있으면 키우기
                """)
            elif selected_proposal.startswith("필터"):
                # Any other filter state
                st.title("그래프 + 요약 테이블")
                st.info("필터를 선택하여 데이터를 확인하세요.")
            else:
                # Valid proposal and dimension selected - show actual data
                proposal_display = name_dictionary.get(selected_proposal, selected_proposal)
                title = f"{proposal_display}"
                if selected_dimension_ui not in ["전체", "필터(구분 선택)"]:
                    title += f" - {selected_dimension_ui}"
                if drilldown_selection not in ["전체", "필터(전체)"]:
                    title += f" ({drilldown_selection})"
                st.title(title)

                # Load and display the proposal view
                # Only load data bundle when actually displaying content
                final_dimension = selected_dimension_ui if selected_dimension_ui != "필터(구분 선택)" else "전체"
                final_drilldown = drilldown_selection if drilldown_selection not in ["필터(전체)"] else "전체"

                with st.spinner("데이터를 불러오는 중..."):
                    # Get data bundle only when needed for actual display
                    data_bundle = get_data_bundle_for_proposal(selected_proposal, final_dimension)
                    order_map = data_bundle.get("order_map", {})

                    fig, aggregate_df = load_proposal_view(
                        proposal_name=selected_proposal,
                        dimension_ui_name=final_dimension,
                        drilldown_selection=final_drilldown,
                        dimension_config=dimension_config,
                        data_bundle=data_bundle,
                        order_map=order_map
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
                    elif selected_proposal == "basic_proposal":
                        # basic_proposal_view handles its own display with tabs
                        # The view function already displayed content, so we don't need to do anything
                        pass
                    else:
                        st.info("선택하신 조건에 해당하는 데이터가 없거나 시각화를 생성할 수 없습니다.")


if __name__ == "__main__":
    main()
