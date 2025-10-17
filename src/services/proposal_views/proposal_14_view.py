import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

def create_figure_and_df(analysis_df, dimension_ui_name, drilldown_selection, dimension_config, order_map):
    """
    제안 14: 조직별/직위별 지각률(%) 분석
    dimension_config에 따라 동적으로 X축을 변경하여 그룹화된 막대그래프를 생성합니다.
    """
    # 1. 데이터 및 설정 유효성 검사
    if analysis_df.empty or 'IS_LATE' not in analysis_df.columns:
        fig = go.Figure().update_layout(title_text="분석할 데이터가 없습니다.")
        return fig, pd.DataFrame()

    config = dimension_config.get(dimension_ui_name, {})
    if not config:
        fig = go.Figure().update_layout(title_text=f"'{dimension_ui_name}'에 대한 설정이 없습니다.")
        return fig, pd.DataFrame()
        
    grouping_col = 'POSITION_NAME' # 이 그래프는 색상 그룹이 '직위'로 고정

    # 2. 차원 설정에 따라 그래프용 데이터(plot_df) 및 속성 설정
    if config.get('type') == 'hierarchical' and drilldown_selection != '전체':
        # 드릴다운 뷰
        top_level_col = config.get('top')
        xaxis_col = config.get('sub')
        plot_df = analysis_df[analysis_df[top_level_col] == drilldown_selection]
        xaxis_order = [o for o in order_map.get(xaxis_col, []) if o in plot_df[xaxis_col].unique()]
        title_text = f"'{drilldown_selection}' 내 하위 그룹별/직위별 지각률"
    else:
        # 최상위 뷰
        plot_df = analysis_df
        xaxis_col = config.get('top', config.get('col'))
        xaxis_order = order_map.get(xaxis_col, sorted(plot_df[xaxis_col].unique()))
        title_text = f"{dimension_ui_name}에 대한 직위별 지각률"

    if plot_df.empty:
        fig = go.Figure().update_layout(title_text=f"'{drilldown_selection}'에 해당하는 데이터가 없습니다.")
        return fig, pd.DataFrame()

    # 3. 지각률 계산
    total_days = plot_df.groupby([xaxis_col, grouping_col], observed=False).size().reset_index(name='TOTAL_DAYS')
    late_days = plot_df[plot_df['IS_LATE']].groupby([xaxis_col, grouping_col], observed=False).size().reset_index(name='LATE_DAYS')
    lateness_df = pd.merge(total_days, late_days, on=[xaxis_col, grouping_col], how='left')
    lateness_df['LATE_DAYS'] = lateness_df['LATE_DAYS'].fillna(0)
    lateness_df['LATENESS_RATE'] = (lateness_df['LATE_DAYS'] / lateness_df['TOTAL_DAYS'] * 100).fillna(0)
        
    # 4. 그래프 생성
    fig = go.Figure()
    colors = px.colors.qualitative.Plotly
    group_order = order_map.get(grouping_col, [])

    for i, group_name in enumerate(group_order):
        df_filtered = lateness_df[lateness_df[grouping_col] == group_name]
        if not df_filtered.empty:
            fig.add_trace(go.Bar(
                x=df_filtered[xaxis_col],
                y=df_filtered['LATENESS_RATE'],
                name=str(group_name),
                marker_color=colors[i % len(colors)],
                text=df_filtered['LATENESS_RATE'].round(1).astype(str) + '%',
                textposition='outside'
            ))

    # 5. 레이아웃 업데이트
    y_max = lateness_df['LATENESS_RATE'].max() if not lateness_df.empty else 0
    fixed_y_range = [0, y_max * 1.2 if y_max > 0 else 10]

    fig.update_layout(
        template='plotly',
        title_text=title_text,
        yaxis_title='지각률 (%)',
        xaxis_title=dimension_ui_name,
        font_size=14,
        height=700,
        barmode='group',
        legend_title_text='직위',
        yaxis_range=fixed_y_range,
        yaxis=dict(ticksuffix="%"),
        xaxis=dict(categoryorder='array', categoryarray=xaxis_order)
    )
    
    # 6. 요약 테이블(aggregate_df) 생성
    pivot_col = config.get('top', config.get('col'))
    
    total_days_agg = analysis_df.groupby([pivot_col, grouping_col], observed=False).size()
    late_days_agg = analysis_df[analysis_df['IS_LATE']].groupby([pivot_col, grouping_col], observed=False).size()
    
    lateness_rate_agg = (late_days_agg / total_days_agg * 100).unstack(level=pivot_col).fillna(0)
    
    # 전체 평균 계산
    total_days_overall = analysis_df.groupby(grouping_col, observed=False).size()
    late_days_overall = analysis_df[analysis_df['IS_LATE']].groupby(grouping_col, observed=False).size()
    lateness_rate_overall = (late_days_overall / total_days_overall * 100).fillna(0)
    lateness_rate_agg['전체 평균'] = lateness_rate_overall
    
    # 컬럼 및 행 순서 재배치
    pivot_order = order_map.get(pivot_col, [])
    cols = ['전체 평균'] + [col for col in pivot_order if col in lateness_rate_agg.columns]
    aggregate_df = lateness_rate_agg[cols]
    aggregate_df = aggregate_df.reindex(group_order).applymap(lambda x: f"{x:.2f}%").replace("0.00%", "-").replace("nan%", "-")

    return fig, aggregate_df