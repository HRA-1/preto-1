import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

def create_figure_and_df(data_bundle, dimension_ui_name, drilldown_selection, dimension_config, order_map):
    """
    제안 13: 조직 워라밸 변화 추이 (월 평균 1인당 초과근무 시간)
    dimension_config에 따라 동적으로 그룹핑하여 꺾은선 그래프를 생성합니다.
    """
    # data_bundle에서 analysis_df 추출
    analysis_df = data_bundle.get("analysis_df", pd.DataFrame())
    
    # 1. 데이터 유효성 검사
    if analysis_df.empty or 'OVERTIME_MINUTES' not in analysis_df.columns:
        fig = go.Figure().update_layout(title_text="분석할 데이터가 없습니다.")
        return fig, pd.DataFrame()

    config = dimension_config.get(dimension_ui_name)
    if not config:
        fig = go.Figure().update_layout(title_text=f"'{dimension_ui_name}'에 대한 설정이 없습니다.")
        return fig, pd.DataFrame()

    # 2. 월별 집계 데이터 생성
    analysis_df['PAY_PERIOD'] = analysis_df['DATE'].dt.strftime('%Y-%m')

    all_summaries = []
    # 모든 분석 차원에 대해 월별 평균 초과근무 시간 계산
    for dim_key, dim_config in dimension_config.items():
        for level in ['top', 'sub']:
            col_name = dim_config.get(level) or dim_config.get('col')
            if col_name and col_name in analysis_df.columns:
                summary = analysis_df.groupby(['PAY_PERIOD', col_name], observed=False).agg(
                    TOTAL_OVERTIME_MINUTES=('OVERTIME_MINUTES', 'sum'),
                    HEADCOUNT=('EMP_ID', 'nunique')
                ).reset_index()
                summary['AVG_OVERTIME_PER_PERSON'] = (summary['TOTAL_OVERTIME_MINUTES'] / summary['HEADCOUNT']) / 60
                summary = summary.rename(columns={col_name: 'GROUP_NAME'})
                summary['GROUP_TYPE'] = col_name
                all_summaries.append(summary)
            if dim_config.get('type') == 'flat': break
    
    agg_analysis_df = pd.concat(all_summaries, ignore_index=True).drop_duplicates()

    # '전체' 평균 계산
    overall_summary = analysis_df.groupby('PAY_PERIOD').agg(
        TOTAL_OVERTIME_MINUTES=('OVERTIME_MINUTES', 'sum'),
        HEADCOUNT=('EMP_ID', 'nunique')
    ).reset_index()
    overall_summary['AVG_OVERTIME_PER_PERSON'] = (overall_summary['TOTAL_OVERTIME_MINUTES'] / overall_summary['HEADCOUNT']) / 60

    # 3. 시각화할 데이터 선택
    if config.get('type') == 'hierarchical' and drilldown_selection != '전체':
        top_level_col = config.get('top')
        grouping_col_name = config.get('sub')
        plot_data = agg_analysis_df[agg_analysis_df['GROUP_TYPE'] == grouping_col_name]
        # 해당 상위 그룹에 속한 하위 그룹만 필터링
        sub_groups_in_top_group = analysis_df[analysis_df[top_level_col] == drilldown_selection][grouping_col_name].unique()
        plot_data = plot_data[plot_data['GROUP_NAME'].isin(sub_groups_in_top_group)]
        category_order = order_map.get(grouping_col_name, [])
        title_text = f"'{drilldown_selection}' 내 하위 그룹별 월 평균 초과근무"
        legend_title = grouping_col_name
    else:
        grouping_col_name = config.get('top', config.get('col'))
        plot_data = agg_analysis_df[agg_analysis_df['GROUP_TYPE'] == grouping_col_name]
        category_order = order_map.get(grouping_col_name, [])
        title_text = f"{dimension_ui_name} 월 평균 초과근무"
        legend_title = grouping_col_name

    # 4. Plotly 그래프 생성
    fig = go.Figure()
    colors = px.colors.qualitative.Plotly
    
    # '전체 평균' 추세선 추가
    fig.add_trace(go.Scatter(
        x=overall_summary['PAY_PERIOD'], y=overall_summary['AVG_OVERTIME_PER_PERSON'], name='전체 평균',
        mode='lines+markers', line=dict(color='black', dash='dash')
    ))

    # 그룹별 추세선 추가
    for i, category_name in enumerate(category_order):
        df_filtered = plot_data[plot_data['GROUP_NAME'] == category_name]
        if not df_filtered.empty:
            fig.add_trace(go.Scatter(
                x=df_filtered['PAY_PERIOD'], y=df_filtered['AVG_OVERTIME_PER_PERSON'], name=str(category_name),
                mode='lines+markers', marker_color=colors[i % len(colors)]
            ))

    # 5. 레이아웃 업데이트
    all_overtime = pd.concat([agg_analysis_df['AVG_OVERTIME_PER_PERSON'], overall_summary['AVG_OVERTIME_PER_PERSON']])
    y_min, y_max = (all_overtime.min(), all_overtime.max()) if not all_overtime.empty else (0, 0)
    y_padding = (y_max - y_min) * 0.1 if (y_max - y_min) > 0 else 10
    fixed_y_range = [y_min - y_padding, y_max + y_padding]

    fig.update_layout(
        template='plotly', title_text=title_text, xaxis_title='월', yaxis_title='월 평균 초과근무 (시간)',
        font_size=14, height=700, legend_title_text=legend_title,
        yaxis_ticksuffix=" 시간", yaxis_range=fixed_y_range
    )
    
    # 6. 요약 테이블(aggregate_df) 생성 (연간 평균)
    agg_analysis_df['YEAR'] = pd.to_datetime(agg_analysis_df['PAY_PERIOD']).dt.year
    overall_summary['YEAR'] = pd.to_datetime(overall_summary['PAY_PERIOD']).dt.year

    top_level_plot_data = agg_analysis_df[agg_analysis_df['GROUP_TYPE'] == config.get('top', config.get('col'))]
    
    aggregate_df = top_level_plot_data.pivot_table(
        index='YEAR', columns='GROUP_NAME', values='AVG_OVERTIME_PER_PERSON', aggfunc='mean', observed=False
    )
    
    overall_agg = overall_summary.groupby('YEAR')['AVG_OVERTIME_PER_PERSON'].mean()
    aggregate_df['전체 평균'] = overall_agg
    
    top_level_order = order_map.get(config.get('top', config.get('col')), [])
    final_cols = ['전체 평균'] + [col for col in top_level_order if col in aggregate_df.columns]
    remaining_cols = [col for col in aggregate_df.columns if col not in final_cols]
    aggregate_df = aggregate_df[final_cols + remaining_cols].round(2).fillna('-').T
    
    return fig, aggregate_df