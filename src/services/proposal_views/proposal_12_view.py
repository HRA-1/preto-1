import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from pandas.api.types import is_categorical_dtype

# 헬퍼 함수 (파일 하단 또는 별도 유틸 파일)
def hour_to_time(hour_float):
    """숫자형 시간을 'HH:MM' 문자열로 변환"""
    if pd.isna(hour_float): return '-'
    hours = int(hour_float)
    minutes = int((hour_float * 60) % 60)
    return f"{hours:02d}:{minutes:02d}"

def create_figure_and_df(data_bundle, dimension_ui_name, drilldown_selection, dimension_config, order_map):
    """
    제안 12: 조직별/직위별 출근 문화 분석
    dimension_config에 따라 동적으로 X축과 그룹을 변경하여 바이올린 플롯을 생성합니다.
    """
    # data_bundle에서 analysis_df 추출
    analysis_df = data_bundle.get("analysis_df", pd.DataFrame())
    
    # 1. 데이터 및 설정 유효성 검사
    if analysis_df.empty or 'START_HOUR' not in analysis_df.columns:
        fig = go.Figure().update_layout(title_text="분석할 데이터가 없습니다.")
        return fig, pd.DataFrame()

    config = dimension_config.get(dimension_ui_name, {})
    if not config:
        fig = go.Figure().update_layout(title_text=f"'{dimension_ui_name}'에 대한 설정이 없습니다.")
        return fig, pd.DataFrame()

    # 2. 차원 설정에 따라 그래프용 데이터(plot_df) 및 속성 설정
    grouping_col = 'POSITION_NAME' # 이 그래프는 색상 그룹이 '직위'로 고정

    if config.get('type') == 'hierarchical' and drilldown_selection != '전체':
        top_level_col = config.get('top')
        xaxis_col = config.get('sub')
        plot_df = analysis_df[analysis_df[top_level_col] == drilldown_selection].copy()
        if is_categorical_dtype(plot_df[xaxis_col]):
            plot_df[xaxis_col] = plot_df[xaxis_col].cat.remove_unused_categories()
        xaxis_order = [o for o in order_map.get(xaxis_col, []) if o in plot_df[xaxis_col].unique()]
        title_text = f"'{drilldown_selection}' 내 하위 그룹별/직위별 출근 시간 분포"
    else:
        plot_df = analysis_df
        xaxis_col = config.get('top', config.get('col'))

        # "전체" 필터인 경우 (xaxis_col is None)
        if xaxis_col is None:
            xaxis_order = []
            title_text = "전체 직위 구분 출근 시간 분포"
        else:
            xaxis_order = order_map.get(xaxis_col, sorted(plot_df[xaxis_col].unique()))
            title_text = f"{dimension_ui_name} 직위 구분 출근 시간 분포"

    if plot_df.empty:
        fig = go.Figure().update_layout(title_text=f"'{drilldown_selection}'에 해당하는 데이터가 없습니다.")
        return fig, pd.DataFrame()
        
    # 3. 그래프 생성 (그룹화된 Violin Plot)
    fig = go.Figure()
    colors = px.colors.qualitative.Plotly
    group_order = order_map.get(grouping_col, [])

    if xaxis_col == grouping_col:
        # X축과 그룹 축이 같으면 (예: '직위직급별' 선택 시), 그룹 없이 단일 바이올린 플롯
        fig.add_trace(go.Violin(
            x=plot_df[xaxis_col], y=plot_df['START_HOUR'], name='출근 시간',
            box_visible=True, meanline_visible=True
        ))
    else:
        # X축과 그룹 축이 다르면, 그룹화된 바이올린 플롯
        for i, group_name in enumerate(group_order):
            if group_name in plot_df[grouping_col].unique():
                df_filtered = plot_df[plot_df[grouping_col] == group_name]
                fig.add_trace(go.Violin(
                    x=df_filtered[xaxis_col], y=df_filtered['START_HOUR'], name=str(group_name),
                    marker_color=colors[i % len(colors)],
                    box_visible=True, meanline_visible=True
                ))

    # 4. 레이아웃 업데이트
    y_min, y_max = (plot_df['START_HOUR'].min(), plot_df['START_HOUR'].max()) if not plot_df.empty else (8, 11)
    fixed_y_range = [y_min - 0.5, y_max + 0.5]

    fig.update_layout(
        template='plotly', title_text=title_text,
        yaxis_title='출근 시간 (24시간 기준)', xaxis_title=dimension_ui_name,
        font_size=14, height=700, violinmode='group', legend_title_text='직위',
        yaxis_range=fixed_y_range,
        yaxis=dict(range=[7.5, 11.5], tickvals=[8, 9, 10, 11], ticktext=['08:00', '09:00', '10:00', '11:00']),
        xaxis=dict(categoryorder='array', categoryarray=xaxis_order)
    )
    
    # 5. 요약 테이블(aggregate_df) 생성
    pivot_col = xaxis_col # 현재 X축 기준
    
    # ----- [수정된 부분 시작: pivot_table 오류 해결] -----
    if pivot_col == grouping_col:
        # X축과 그룹 축이 같은 경우, 단순 요약 테이블 생성
        aggregate_df = plot_df.groupby(grouping_col, observed=True)['START_HOUR'].agg(['mean', 'count'])
        overall_avg = analysis_df['START_HOUR'].mean()
        overall_count = len(analysis_df)
        aggregate_df.loc['전체 평균'] = [overall_avg, overall_count]
        aggregate_df = aggregate_df.rename(columns={'mean': '평균 출근 시간', 'count': '데이터 수'})
        aggregate_df['평균 출근 시간'] = aggregate_df['평균 출근 시간'].apply(lambda x: hour_to_time(x) if pd.notna(x) else '-')
        aggregate_df['데이터 수'] = aggregate_df['데이터 수'].astype(int)

    else:
        # X축과 그룹 축이 다른 경우, 피벗 테이블 생성
        aggregate_df = plot_df.pivot_table(
            index=grouping_col, 
            columns=pivot_col,
            values='START_HOUR',
            aggfunc='mean',
            observed=True
        )
        aggregate_df['전체 평균'] = plot_df.groupby(grouping_col, observed=True)['START_HOUR'].mean()
        aggregate_df = aggregate_df.applymap(hour_to_time) # 시간 포맷으로 변환
        cols = ['전체 평균'] + [col for col in xaxis_order if col in aggregate_df.columns]
        aggregate_df = aggregate_df[cols]

    aggregate_df = aggregate_df.reindex(group_order).fillna('-').T
    # ----- [수정된 부분 끝] -----

    return fig, aggregate_df