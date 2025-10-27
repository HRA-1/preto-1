import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

def create_figure_and_df(data_bundle, dimension_ui_name, drilldown_selection, dimension_config, order_map):
    """
    제안 5: 조직 건강도 위험 신호 탐지 (연간 퇴사율)
    드릴다운 로직과 '전체' 평균 로직을 수정한 최종본입니다.
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

    # --- 2. 시각화할 데이터 선택 (드릴다운 로직 수정) ---
    
    if config['type'] == 'hierarchical' and drilldown_selection != '전체':
        # --- 드릴다운 뷰 ---
        top_level_col = config.get('top')
        grouping_col_name = config.get('sub')
        
        # 1. plot_data: 
        # 1-1. 먼저 하위 그룹(예: 'OFFICE_NAME') 데이터만 추립니다. 
        # (이 데이터 슬라이스에는 'PARENT_DIM' 컬럼이 보장됩니다.)
        plot_data_source = turnover_data[turnover_data['DIMENSION'] == grouping_col_name]
        # 1-2. 그 다음, PARENT_DIM을 기준으로 드릴다운 필터링을 적용합니다.
        plot_data = plot_data_source[plot_data_source['PARENT_DIM'] == drilldown_selection]
        category_order = [o for o in order_map.get(grouping_col_name, []) if o in plot_data['CATEGORY'].unique()]
        
        # 2. total_turnover: 상위 그룹(예: 'Planning Division')의 평균을 '전체'로 사용
        total_turnover = turnover_data[
            (turnover_data['DIMENSION'] == top_level_col) & 
            (turnover_data['CATEGORY'] == drilldown_selection)
        ]
        total_label = drilldown_selection # '전체' 대신 상위 그룹 이름 사용
        title_text = f"'{drilldown_selection}' 내 하위 그룹별 연간 퇴사율"
        legend_title = grouping_col_name
    else:
        # --- 최상위 뷰 ---
        grouping_col_name = config.get('top', config.get('col'))
        
        # 1. plot_data: 최상위 그룹 데이터 (예: 'Division' 데이터)
        plot_data = turnover_data[turnover_data['DIMENSION'] == grouping_col_name]
        category_order = order_map.get(grouping_col_name, [])
        
        # 2. total_turnover: 전사 '전체' 평균 사용
        total_turnover = turnover_data[turnover_data['DIMENSION'] == '전체']
        total_label = '전체'
        title_text = f"{dimension_ui_name} 연간 퇴사율"
        legend_title = grouping_col_name

    # --- 3. Plotly 그래프 생성 ---
    fig = go.Figure()
    colors = px.colors.qualitative.Plotly
    
    # '전체' (또는 상위 그룹) 추세선 추가
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
    
    # --- 4. 요약 테이블(aggregate_df) 생성 ---
    pivot_df = plot_data.pivot_table(
        index='YEAR', columns='CATEGORY', values='TURNOVER_RATE', observed=False
    )
    
    if not total_turnover.empty:
        pivot_df[total_label] = total_turnover.set_index('YEAR')['TURNOVER_RATE']
    
    final_cols = [total_label] + [col for col in category_order if col in pivot_df.columns]
    remaining_cols = [col for col in pivot_df.columns if col not in final_cols and col != total_label]
    aggregate_df = pivot_df[final_cols + remaining_cols].round(2).fillna('-')
    
    return fig, aggregate_df