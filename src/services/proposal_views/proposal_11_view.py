import pandas as pd
import plotly.graph_objects as go

def create_figure_and_df(data_bundle, dimension_ui_name, drilldown_selection, dimension_config, order_map):
    """
    제안 11: 근무 유연성 분석 (조직별 초과근무 분포)
    dimension_config에 따라 동적으로 X축을 변경하여 바이올린 플롯을 생성합니다.
    """
    # data_bundle에서 analysis_df 추출
    analysis_df = data_bundle.get("analysis_df", pd.DataFrame())
    
    # 1. 데이터 및 설정 유효성 검사
    if analysis_df.empty or 'OVERTIME_MINUTES' not in analysis_df.columns:
        fig = go.Figure().update_layout(title_text="분석할 데이터가 없습니다.")
        return fig, pd.DataFrame()

    config = dimension_config.get(dimension_ui_name)
    if not config:
        fig = go.Figure().update_layout(title_text=f"'{dimension_ui_name}'에 대한 설정이 없습니다.")
        return fig, pd.DataFrame()

    # 2. 차원 설정에 따라 그래프용 데이터(plot_df) 및 X축 설정
    if config.get('type') == 'hierarchical' and drilldown_selection != '전체':
        # 드릴다운 뷰 (예: 특정 Division 내 Office별)
        top_level_col = config.get('top')
        xaxis_col = config.get('sub')
        plot_df = analysis_df[analysis_df[top_level_col] == drilldown_selection]
        xaxis_order = [o for o in order_map.get(xaxis_col, []) if o in plot_df[xaxis_col].unique()]
        title_text = f"'{drilldown_selection}' 내 하위 그룹별 근무 유연성 분석"
    else:
        # 최상위 뷰 (예: Division별 또는 성별)
        plot_df = analysis_df
        xaxis_col = config.get('top', config.get('col'))

        # "전체" 필터인 경우 (xaxis_col is None)
        if xaxis_col is None:
            xaxis_order = []
            title_text = "전체 근무 유연성 분석"
        else:
            xaxis_order = order_map.get(xaxis_col, sorted(plot_df[xaxis_col].unique()))
            title_text = f"{dimension_ui_name} 근무 유연성 분석"

    if plot_df.empty:
        fig = go.Figure().update_layout(title_text=f"'{drilldown_selection}'에 해당하는 데이터가 없습니다.")
        return fig, pd.DataFrame()

    # 3. 그래프 생성 (Violin Plot)
    fig = go.Figure()

    if xaxis_col is None:
        # "전체" 필터: 차원별 그룹화 없이 전체 데이터로 단일 violin plot
        fig.add_trace(go.Violin(
            y=plot_df['OVERTIME_MINUTES'],
            box_visible=True,
            meanline_visible=True,
            points='outliers',
            name='초과근무 분포'
        ))
    else:
        # 일반 필터: 차원별 그룹화된 violin plot
        fig.add_trace(go.Violin(
            x=plot_df[xaxis_col],
            y=plot_df['OVERTIME_MINUTES'],
            box_visible=True,
            meanline_visible=True,
            points='outliers',
            name='초과근무 분포'
        ))

    # 4. 레이아웃 업데이트
    y_min, y_max = plot_df['OVERTIME_MINUTES'].min(), plot_df['OVERTIME_MINUTES'].max()
    y_padding = (y_max - y_min) * 0.1
    fixed_y_range = [y_min - y_padding, y_max + y_padding]

    layout_config = {
        'template': 'plotly',
        'title_text': title_text,
        'yaxis_title': '일별 초과근무 시간 (분)',
        'font_size': 14,
        'height': 700,
        'showlegend': False,
        'yaxis_range': fixed_y_range,
    }

    if xaxis_col is not None:
        layout_config['xaxis_title'] = dimension_ui_name
        layout_config['xaxis'] = dict(
            categoryorder='array',
            categoryarray=xaxis_order
        )

    fig.update_layout(**layout_config)
    fig.add_hline(y=0, line_width=2, line_dash="dash", line_color="black")

    # 5. 요약 테이블(aggregate_df) 생성
    if xaxis_col is None:
        # "전체" 필터: 전체 평균만 표시
        aggregate_df = pd.DataFrame({
            '평균': [plot_df['OVERTIME_MINUTES'].mean()],
            '중앙값': [plot_df['OVERTIME_MINUTES'].median()],
            '표준편차': [plot_df['OVERTIME_MINUTES'].std()],
            '최대': [plot_df['OVERTIME_MINUTES'].max()],
            '최소': [plot_df['OVERTIME_MINUTES'].min()],
        }, index=['전체 평균']).round(1).fillna('-')
    else:
        # 일반 필터: 차원별 평균 표시
        agg_funcs = {
            '평균': ('OVERTIME_MINUTES', 'mean'),
            '중앙값': ('OVERTIME_MINUTES', 'median'),
            '표준편차': ('OVERTIME_MINUTES', 'std'),
            '최대': ('OVERTIME_MINUTES', 'max'),
            '최소': ('OVERTIME_MINUTES', 'min'),
        }
        aggregate_df = plot_df.groupby(xaxis_col, observed=False).agg(**agg_funcs).reset_index()

        # 전체 요약 행 추가
        total_summary = {
            xaxis_col: '전체 평균',
            '평균': plot_df['OVERTIME_MINUTES'].mean(),
            '중앙값': plot_df['OVERTIME_MINUTES'].median(),
            '표준편차': plot_df['OVERTIME_MINUTES'].std(),
            '최대': plot_df['OVERTIME_MINUTES'].max(),
            '최소': plot_df['OVERTIME_MINUTES'].min(),
        }
        aggregate_df = pd.concat([aggregate_df, pd.DataFrame([total_summary])], ignore_index=True)

        aggregate_df = aggregate_df.set_index(xaxis_col)

        final_index_order = ['전체 평균'] + xaxis_order
        existing_indices = [idx for idx in final_index_order if idx in aggregate_df.index]
        aggregate_df = aggregate_df.reindex(existing_indices)

        aggregate_df = aggregate_df.round(1).fillna('-')
    
    return fig, aggregate_df