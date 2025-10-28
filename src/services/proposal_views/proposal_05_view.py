import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

def create_figure_and_df(data_bundle, dimension_ui_name, drilldown_selection, dimension_config, order_map):
    """
    제안 5: 조직 건강도 위험 신호 탐지 (연간 퇴사율)
    [수정] 드릴다운 기능을 제거하여 안정성을 확보합니다.
    (drilldown_selection은 app.py와의 호환성을 위해 받지만, 이 함수 내에서는 사용되지 않습니다.)
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

    # --- 2. 시각화할 데이터 선택 (드릴다운 로직 제거) ---
    
    # 항상 최상위 뷰를 보여줍니다.
    grouping_col_name = config.get('top', config.get('col'))
    
    plot_data = turnover_data[turnover_data['DIMENSION'] == grouping_col_name]
    category_order = order_map.get(grouping_col_name, [])
    
    total_turnover = turnover_data[turnover_data['DIMENSION'] == '전체']
    total_label = '전체'
    title_text = f"{dimension_ui_name} 연간 퇴사율"
    legend_title = grouping_col_name

    # --- 3. Plotly 그래프 생성 ---
    fig = go.Figure()
    colors = px.colors.qualitative.Plotly
    
    # '전체' 추세선 추가
    if not total_turnover.empty:
        fig.add_trace(go.Scatter(
            x=total_turnover['YEAR'], y=total_turnover['TURNOVER_RATE'], name=total_label,
            mode='lines+markers+text', text=total_turnover['TURNOVER_RATE'].round(1).astype(str) + '%',
            textposition="top center", line=dict(color='black', dash='dash', width=4)
        ))

    # 그룹별 추세선 추가
    for i, category_name in enumerate(category_order):
        df_filtered = plot_data[plot_data['CATEGORY'] == category_name]
        if not df_filtered.empty:
            fig.add_trace(go.Scatter(
                x=df_filtered['YEAR'], y=df_filtered['TURNOVER_RATE'], name=str(category_name),
                mode='lines+markers+text', text=df_filtered['TURNOVER_RATE'].round(1).astype(str) + '%',
                textposition="top center", marker_color=colors[i % len(colors)]
            ))

    # 4. 레이아웃 업데이트
    all_rates = pd.concat([plot_data['TURNOVER_RATE'], total_turnover['TURNOVER_RATE']])
    y_max = all_rates.max() if not all_rates.empty else 0
    fixed_y_range = [0, y_max * 1.2 if y_max > 0 else 10]

    fig.update_layout(
        template='plotly',
        title_text=title_text, xaxis_title='연도', yaxis_title='연간 퇴사율 (%)',
        font_size=14, height=700, legend_title_text=legend_title,
        yaxis_ticksuffix=" %"
    )
    fig.update_xaxes(dtick=1)
    
    # --- 5. 요약 테이블(aggregate_df) 생성 ---
    pivot_df = plot_data.pivot_table(
        index='YEAR', columns='CATEGORY', values='TURNOVER_RATE', observed=False
    )
    
    if not total_turnover.empty:
        pivot_df[total_label] = total_turnover.set_index('YEAR')['TURNOVER_RATE']
    
    final_cols = [total_label] + [col for col in category_order if col in pivot_df.columns]
    remaining_cols = [col for col in pivot_df.columns if col not in final_cols and col != total_label]
    aggregate_df = pivot_df[final_cols + remaining_cols].round(2).fillna('-').tail(10).T
    
    return fig, aggregate_df