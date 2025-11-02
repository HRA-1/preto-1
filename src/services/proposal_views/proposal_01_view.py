import pandas as pd
import numpy as np
import plotly.graph_objects as go

def create_figure_and_df(data_bundle, dimension_ui_name, drilldown_selection, dimension_config, order_map):
    """
    제안 1: 성장 속도 비교 그래프 및 피벗 테이블을 생성합니다.
    순서 정보(order_map)를 활용하여 X축을 동적으로 정렬합니다.
    """
    # data_bundle에서 analysis_df 추출
    analysis_df = data_bundle.get("analysis_df", pd.DataFrame())
    
    # 1. 데이터가 없는 경우 즉시 빈 결과 반환
    if analysis_df.empty or analysis_df[['TIME_TO_MANAGER', 'TIME_TO_DIRECTOR']].isnull().all().all():
        fig = go.Figure().update_layout(title_text="분석할 승진 데이터가 없습니다.")
        return fig, pd.DataFrame()

    config = dimension_config.get(dimension_ui_name, {})
    if not config:
        fig = go.Figure().update_layout(title_text=f"'{dimension_ui_name}'에 대한 설정이 없습니다.")
        return fig, pd.DataFrame()

    # 2. 차원 설정에 따라 그래프용 데이터(plot_df) 및 X축, 제목 등 설정
    if config.get('type') == 'hierarchical' and drilldown_selection != '전체':
        # 드릴다운 뷰 (예: 특정 Division 내 Office별)
        top_level_col = config.get('top')
        xaxis_col = config.get('sub')
        plot_df = analysis_df[analysis_df[top_level_col] == drilldown_selection]
        xaxis_order = [o for o in order_map.get(xaxis_col, []) if o in plot_df[xaxis_col].unique()]
        title_text = f"'{drilldown_selection}' 내 하위 그룹별 승진 소요 기간"
    else:
        # 전체 뷰 (예: Division별 또는 성별)
        plot_df = analysis_df
        xaxis_col = config.get('top', config.get('col')) # 계층형 top 또는 단일형 col

        # "전체" 필터인 경우 (xaxis_col is None)
        if xaxis_col is None:
            xaxis_order = []
            title_text = "전체 승진 소요 기간"
        else:
            xaxis_order = order_map.get(xaxis_col, sorted(plot_df[xaxis_col].unique()))
            title_text = f"전체 {dimension_ui_name} 승진 소요 기간 비교"

    # 3. 그래프 생성
    fig = go.Figure()
    if xaxis_col is None:
        # "전체" 필터: 차원별 그룹화 없이 전체 데이터로 승진 단계별 box plot
        fig.add_trace(go.Box(
            y=plot_df['TIME_TO_MANAGER'],
            name='Staff → Manager',
            boxpoints='outliers',
            marker_color='blue'
        ))
        fig.add_trace(go.Box(
            y=plot_df['TIME_TO_DIRECTOR'],
            name='Manager → Director',
            boxpoints='outliers',
            marker_color='red'
        ))
    else:
        # 일반 필터: 차원별 그룹화된 box plot
        fig.add_trace(go.Box(
            y=plot_df['TIME_TO_MANAGER'],
            x=plot_df[xaxis_col],
            name='Staff → Manager',
            boxpoints='outliers',
            marker_color='blue'
        ))
        fig.add_trace(go.Box(
            y=plot_df['TIME_TO_DIRECTOR'],
            x=plot_df[xaxis_col],
            name='Manager → Director',
            boxpoints='outliers',
            marker_color='red'
        ))

    y_max_series = pd.concat([plot_df['TIME_TO_MANAGER'], plot_df['TIME_TO_DIRECTOR']]).dropna()
    y_max = y_max_series.max() if not y_max_series.empty else 10
    fixed_y_range = [0, y_max * 1.1]

    layout_config = {
        'template': 'plotly',
        'title_text': title_text,
        'yaxis_title': '승진 소요 기간 (년)',
        'font_size': 14,
        'height': 700,
        'boxmode': 'group',
        'legend_title_text': '승진 단계',
        'yaxis_range': fixed_y_range,
    }

    if xaxis_col is not None:
        layout_config['xaxis'] = dict(
            title=dimension_ui_name,
            categoryorder='array',
            categoryarray=xaxis_order
        )

    fig.update_layout(**layout_config)

    # 4. 요약 테이블(aggregate_df) 생성
    pivot_col = config.get('top', config.get('col')) # 항상 상위 레벨 기준으로 요약

    if pivot_col is None:
        # "전체" 필터: 전체 평균만 표시
        manager_mean = analysis_df['TIME_TO_MANAGER'].mean()
        director_mean = analysis_df['TIME_TO_DIRECTOR'].mean()
        aggregate_df = pd.DataFrame({
            '전체 평균': [manager_mean, director_mean]
        }, index=['Staff → Manager', 'Manager → Director']).round(2).T
    else:
        # 일반 필터: 차원별 평균 표시
        df_melted = analysis_df.melt(
            id_vars=[pivot_col],
            value_vars=['TIME_TO_MANAGER', 'TIME_TO_DIRECTOR'],
            var_name='PROMOTION_STEP',
            value_name='YEARS'
        )
        df_melted['PROMOTION_STEP'] = df_melted['PROMOTION_STEP'].map({
            'TIME_TO_MANAGER': 'Staff → Manager',
            'TIME_TO_DIRECTOR': 'Manager → Director'
        })

        aggregate_df = df_melted.pivot_table(
            index='PROMOTION_STEP',
            columns=pivot_col,
            values='YEARS',
            aggfunc='mean',
            observed=False
        )
        aggregate_df['전체 평균'] = df_melted.groupby('PROMOTION_STEP')['YEARS'].mean()

        # 컬럼 및 행 순서 재배치
        pivot_order = order_map.get(pivot_col, sorted(analysis_df[pivot_col].unique()))
        cols = ['전체 평균'] + [col for col in pivot_order if col in aggregate_df.columns]
        aggregate_df = aggregate_df[cols]
        promotion_step_order = ['Staff → Manager', 'Manager → Director']
        aggregate_df = aggregate_df.reindex(promotion_step_order).round(2).fillna('-').T

    return fig, aggregate_df