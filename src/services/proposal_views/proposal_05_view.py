import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

def create_figure_and_df(data_bundle, dimension_ui_name, drilldown_selection, dimension_config, order_map):
    """
    제안 5: 조직 건강도 위험 신호 탐지 (연간 퇴사율)
    미리 계산된 퇴사율 데이터를 받아, 선택된 차원에 맞게 시각화합니다.
    """
    # 1. 데이터 및 설정 유효성 검사
    turnover_data = data_bundle.get("turnover_data")

    if turnover_data is None or turnover_data.empty:
        fig = go.Figure().update_layout(title_text="분석할 데이터가 없습니다.")
        return fig, pd.DataFrame()

    config = dimension_config.get(dimension_ui_name)
    if not config:
        fig = go.Figure().update_layout(title_text=f"'{dimension_ui_name}'에 대한 설정이 없습니다.")
        return fig, pd.DataFrame()

    # --- 2. 시각화할 데이터 선택 ---
    if config['type'] == 'hierarchical' and drilldown_selection != '전체':
        # 드릴다운 시에는 sub-dimension 데이터만 필터링
        grouping_col_dim = config['sub']
        category_order = order_map.get(grouping_col_dim, [])
        plot_data = turnover_data[turnover_data['DIMENSION'] == grouping_col_dim]
        title_text = f"'{drilldown_selection}' 내 하위 그룹별 연간 퇴사율"
    else:
        # 기본 뷰에서는 top-level dimension 데이터 필터링
        grouping_col_dim = config.get('top', config.get('col'))
        category_order = order_map.get(grouping_col_dim, [])
        plot_data = turnover_data[turnover_data['DIMENSION'] == grouping_col_dim]
        title_text = f"{dimension_ui_name} 연간 퇴사율"

    # --- 3. Plotly 그래프 생성 ---
    fig = go.Figure()
    colors = px.colors.qualitative.Plotly
    
    # '전체' 추세선 추가
    total_turnover = turnover_data[turnover_data['DIMENSION'] == '전체']
    if not total_turnover.empty:
        fig.add_trace(go.Scatter(
            x=total_turnover['YEAR'], y=total_turnover['TURNOVER_RATE'], name='전체',
            mode='lines+markers+text', text=total_turnover['TURNOVER_RATE'].round(1).astype(str) + '%',
            textposition="top center", line=dict(color='black', dash='dash', width=4)
        ))

    # 그룹별 추세선 추가
    for i, category_name in enumerate(category_order):
        df_filtered = plot_data[plot_data['CATEGORY'] == category_name]
        if not df_filtered.empty:
            fig.add_trace(go.Scatter(
                x=df_filtered['YEAR'], y=df_filtered['TURNOVER_RATE'], name=category_name,
                mode='lines+markers+text', text=df_filtered['TURNOVER_RATE'].round(1).astype(str) + '%',
                textposition="top center", marker_color=colors[i % len(colors)]
            ))

    fig.update_layout(
        title_text=title_text, xaxis_title='연도', yaxis_title='연간 퇴사율 (%)',
        font_size=14, height=700, legend_title_text=dimension_ui_name,
        yaxis_ticksuffix=" %"
    )
    fig.update_xaxes(dtick=1)
    
    # --- 4. 요약 테이블(aggregate_df) 생성 ---
    pivot_df = plot_data.pivot_table(
        index='YEAR', columns='CATEGORY', values='TURNOVER_RATE', observed=False
    )
    
    if not total_turnover.empty:
        pivot_df['전체'] = total_turnover.set_index('YEAR')['TURNOVER_RATE']
    
    final_cols = ['전체'] + [col for col in category_order if col in pivot_df.columns]
    remaining_cols = [col for col in pivot_df.columns if col not in final_cols and col != '전체']
    aggregate_df = pivot_df[final_cols + remaining_cols].round(2).fillna('-')
    
    return fig, aggregate_df