import pandas as pd
import plotly.graph_objects as go

def create_figure_and_df(data_bundle, dimension_ui_name, drilldown_selection, dimension_config, order_map):
    """
    제안 6: 입사 연도별 잔존율 코호트 분석 (히트맵)
    data_bundle과 사용자 선택(dimension_ui_name, drilldown_selection)을 기반으로
    '이미 선택된' 단일 코호트 피벗 테이블을 받아 히트맵 그래프를 생성합니다.
    """
    # --- [수정된 부분 시작] ---
    # data_bundle에서 app.py가 선택한 데이터를 추출
    cohort_data_bundle = data_bundle.get("cohort_data_bundle", {})
    cohort_map = cohort_data_bundle.get(dimension_ui_name, {})
    cohort_pivot = cohort_map.get(drilldown_selection, pd.DataFrame())
    title = f"[{dimension_ui_name} - {drilldown_selection}] 입사 연도별 잔존율"
    # --- [수정된 부분 끝] ---

    if cohort_pivot.empty:
        return go.Figure().update_layout(title_text="표시할 데이터가 없습니다.")

    # 텍스트 라벨 생성
    text_labels = cohort_pivot.applymap(lambda x: f'{x:.0f}%' if pd.notna(x) else '')

    # 단 하나의 히트맵 트레이스만 추가
    fig = go.Figure(data=go.Heatmap(
        z=cohort_pivot.values,
        x=[f"{int(c)}년차" for c in cohort_pivot.columns],
        y=cohort_pivot.index,
        colorscale='Blues',
        text=text_labels,
        texttemplate="%{text}",
        showscale=False,
        connectgaps=False
    ))

    # 레이아웃 업데이트
    fig.update_layout(
        template='plotly',
        title_text=title,
        xaxis_title='근속년수',
        yaxis_title='입사 연도 (코호트)',
        font_size=14,
        height=700,
    )
    
    # 이 분석은 요약 테이블이 별도로 필요하지 않으므로, 빈 데이터프레임을 반환
    return fig, pd.DataFrame()