import pandas as pd
import numpy as np
import plotly.graph_objects as go

def create_figure_and_df(data_bundle, dimension_ui_name, drilldown_selection, dimension_config, order_map):
    """
    제안 15: 부서 변경 전후 초과근무 패턴 분석
    드릴다운 선택에 따라 Division 또는 Office별 그룹 막대그래프를 생성합니다.
    (dimension_ui_name, dimension_config는 app.py와의 호환성을 위해 받지만, 이 함수 내에서는 사용되지 않습니다.)
    """
    # data_bundle에서 analysis_df 추출
    analysis_df = data_bundle.get("analysis_df", pd.DataFrame())
    
    # 1. 데이터 유효성 검사
    if analysis_df.empty:
        fig = go.Figure().update_layout(title_text="분석할 데이터가 없습니다.")
        return fig, pd.DataFrame()

    # 2. 드릴다운 선택에 따라 그래프용 데이터(plot_df) 및 X축 설정
    if drilldown_selection == '전체':
        # 최상위 뷰 (Division별)
        plot_df = analysis_df.groupby('DIVISION_NAME', observed=False).mean(numeric_only=True).reset_index()
        xaxis_col = 'DIVISION_NAME'
        xaxis_order = order_map.get('DIVISION_NAME', [])
        title_text = '부서 변경 전후 3개월간 일평균 초과근무 시간 비교'
    else:
        # 드릴다운 뷰 (Office별)
        plot_df = analysis_df[analysis_df['DIVISION_NAME'] == drilldown_selection].copy()
        plot_df = plot_df.groupby('OFFICE_NAME', observed=False).mean(numeric_only=True).reset_index()
        xaxis_col = 'OFFICE_NAME'
        unique_offices = plot_df[xaxis_col].unique()
        xaxis_order = [o for o in order_map.get('OFFICE_NAME', []) if o in unique_offices]
        title_text = f"'{drilldown_selection}' 내 Office별 초과근무 시간 비교"

    if plot_df.empty:
        fig = go.Figure().update_layout(title_text=f"'{drilldown_selection}'에 해당하는 데이터가 없습니다.")
        return fig, pd.DataFrame()
        
    # 3. 그래프 생성
    fig = go.Figure()
    periods = {'변경 전': 'OT_BEFORE', '변경 후': 'OT_AFTER', '부서 평균': 'DEPT_AVG'}

    for period_name, col_name in periods.items():
        fig.add_trace(go.Bar(
            x=plot_df[xaxis_col], y=plot_df[col_name], name=period_name,
            text=plot_df[col_name].round(1), textposition='outside'
        ))

    # 4. 레이아웃 업데이트
    all_values = pd.concat([plot_df['OT_BEFORE'], plot_df['OT_AFTER'], plot_df['DEPT_AVG']])
    y_min, y_max = (all_values.min(), all_values.max()) if not all_values.empty else (0, 0)
    y_padding = (y_max - y_min) * 0.1 if (y_max - y_min) > 0 else 10
    fixed_y_range = [y_min - y_padding, y_max + y_padding]

    fig.update_layout(
        template='plotly', title_text=title_text, yaxis_title='일평균 초과근무 시간 (분)',
        font_size=14, height=700, barmode='group', legend_title_text='시점',
        yaxis_range=fixed_y_range,
        xaxis=dict(categoryorder='array', categoryarray=xaxis_order)
    )
    
    # 5. 요약 테이블(aggregate_df) 생성
    agg_df = analysis_df.groupby('DIVISION_NAME', observed=False)[['OT_BEFORE', 'OT_AFTER', 'DEPT_AVG']].mean()
    overall_avg = analysis_df[['OT_BEFORE', 'OT_AFTER', 'DEPT_AVG']].mean()
    agg_df.loc['전체 평균'] = overall_avg
    
    agg_df = agg_df.rename(columns={'OT_BEFORE': '변경 전', 'OT_AFTER': '변경 후', 'DEPT_AVG': '부서 평균'})
    
    agg_df = agg_df.reindex(['전체 평균'] + order_map.get('DIVISION_NAME', []))
    aggregate_df = agg_df.round(1).fillna('-')

    return fig, aggregate_df