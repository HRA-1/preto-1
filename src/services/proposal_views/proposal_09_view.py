import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

def create_figure_and_df(data_bundle, dimension_ui_name, drilldown_selection, dimension_config, order_map):
    """
    제안 9: 조직 활력도 진단 (연간 직무 이동률)
    드릴다운 없이, 선택된 단일 차원에 대한 그룹별 추이를 시각화합니다.
    (drilldown_selection은 app.py와의 호환성을 위해 받지만, 이 함수 내에서는 사용되지 않습니다.)
    """
    # 1. 데이터 및 설정 유효성 검사
    analysis_df = data_bundle.get("analysis_df")
    overall_df = data_bundle.get("overall_df")

    if analysis_df is None or analysis_df.empty:
        fig = go.Figure().update_layout(title_text="분석할 데이터가 없습니다.")
        return fig, pd.DataFrame()

    config = dimension_config.get(dimension_ui_name)
    if not config:
        fig = go.Figure().update_layout(title_text=f"'{dimension_ui_name}'에 대한 설정이 없습니다.")
        return fig, pd.DataFrame()

    # 2. 시각화할 데이터 선택
    grouping_col_name = config.get('top', config.get('col'))
    plot_data = analysis_df[analysis_df['GROUP_TYPE'] == grouping_col_name]
    category_order = order_map.get(grouping_col_name, [])
    title_text = f"{dimension_ui_name} 연간 직무 이동률"
    
    # 3. Plotly 그래프 생성
    fig = go.Figure()
    colors = px.colors.qualitative.Plotly
    
    # '전체 평균' 추세선 추가
    if overall_df is not None and not overall_df.empty:
        fig.add_trace(go.Scatter(
            x=overall_df['YEAR'], y=overall_df['MOBILITY_RATE'], name='전체 평균',
            # --- [수정 2: 라벨 추가] ---
            mode='lines+markers+text', 
            text=overall_df['MOBILITY_RATE'].round(1).astype(str) + '%',
            textposition="top center", 
            line=dict(color='black', dash='dash', width=4)
        ))

    # 그룹별 추세선 추가
    for i, category_name in enumerate(category_order):
        # --- [수정 1: 버그 수정 'CATEGORY' -> 'GROUP_NAME'] ---
        df_filtered = plot_data[plot_data['GROUP_NAME'] == category_name]
        if not df_filtered.empty:
            fig.add_trace(go.Scatter(
                x=df_filtered['YEAR'], y=df_filtered['MOBILITY_RATE'], name=str(category_name),
                # --- [수정 2: 라벨 추가] ---
                mode='lines+markers+text', 
                text=df_filtered['MOBILITY_RATE'].round(1).astype(str) + '%',
                textposition="top center", 
                marker_color=colors[i % len(colors)]
            ))

    # 4. 레이아웃 업데이트
    all_rates = pd.concat([analysis_df['MOBILITY_RATE'], overall_df['MOBILITY_RATE']])
    y_max = all_rates.max() if not all_rates.empty else 0
    fixed_y_range = [0, y_max * 1.2 if y_max > 0 else 10]

    fig.update_layout(
        template='plotly',
        title_text=title_text,
        xaxis_title='연도',
        yaxis_title='연간 직무 이동률 (%)',
        font_size=14,
        height=700,
        legend_title_text=dimension_ui_name,
        yaxis_ticksuffix=" %",
        yaxis_range=fixed_y_range
    )
    fig.update_xaxes(dtick=1)
    
    # 5. 요약 테이블(aggregate_df) 생성
    aggregate_df = plot_data.pivot_table(
        index='YEAR', columns='GROUP_NAME', values='MOBILITY_RATE', observed=False
    )
    
    if overall_df is not None and not overall_df.empty:
        aggregate_df['전체 평균'] = overall_df.set_index('YEAR')['MOBILITY_RATE']
    
    # 컬럼 순서 재배치
    final_cols = ['전체 평균'] + [col for col in category_order if col in aggregate_df.columns]
    remaining_cols = [col for col in aggregate_df.columns if col not in final_cols]
    aggregate_df = aggregate_df[final_cols + remaining_cols].round(2).fillna('-').tail(10).T
    
    return fig, aggregate_df