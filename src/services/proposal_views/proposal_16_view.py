import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from pandas.api.types import is_categorical_dtype

def create_figure_and_df(data_bundle, dimension_ui_name, drilldown_selection, dimension_config, order_map):
    """
    제안 16: 주말 근무 패턴 분석
    모든 차원을 지원하며, NaN 텍스트와 groupby 오류를 해결합니다.
    """
    # data_bundle에서 analysis_df 추출
    analysis_df = data_bundle.get("analysis_df", pd.DataFrame())
    
    # 1. 데이터 및 설정 유효성 검사
    if analysis_df.empty or 'WEEKEND_WORK_DAYS' not in analysis_df.columns:
        fig = go.Figure().update_layout(title_text="분석할 데이터가 없습니다.")
        return fig, pd.DataFrame()

    config = dimension_config.get(dimension_ui_name, {})
    if not config:
        fig = go.Figure().update_layout(title_text=f"'{dimension_ui_name}'에 대한 설정이 없습니다.")
        return fig, pd.DataFrame()
        
    grouping_col = 'POSITION_NAME'

    # 2. 차원 설정에 따라 그래프용 데이터(plot_df) 및 속성 설정
    if config.get('type') == 'hierarchical' and drilldown_selection != '전체':
        top_level_col = config.get('top')
        xaxis_col = config.get('sub')
        plot_df = analysis_df[analysis_df[top_level_col] == drilldown_selection].copy()
        if is_categorical_dtype(plot_df[xaxis_col]):
            plot_df[xaxis_col] = plot_df[xaxis_col].cat.remove_unused_categories()
        xaxis_order = [o for o in order_map.get(xaxis_col, []) if o in plot_df[xaxis_col].unique()]
        title_text = f"'{drilldown_selection}' 내 하위 그룹별/직위별 월 평균 주말 근무일수"
    else:
        plot_df = analysis_df
        xaxis_col = config.get('top', config.get('col'))

        # "전체" 필터인 경우 (xaxis_col is None)
        if xaxis_col is None:
            xaxis_order = []
            title_text = "전체 직위별 월 평균 주말 근무일수"
        else:
            xaxis_order = order_map.get(xaxis_col, sorted(plot_df[xaxis_col].unique()))
            title_text = f"{dimension_ui_name} 및 직위별 월 평균 주말 근무일수"

    if plot_df.empty:
        fig = go.Figure().update_layout(title_text=f"'{drilldown_selection}'에 해당하는 데이터가 없습니다.")
        return fig, pd.DataFrame()

    # 3. 월 평균 주말 근무일수 계산
    if xaxis_col == grouping_col:
        summary_df = plot_df.groupby(xaxis_col, observed=False)['WEEKEND_WORK_DAYS'].mean().reset_index()
    else:
        summary_df = plot_df.groupby([xaxis_col, grouping_col], observed=False)['WEEKEND_WORK_DAYS'].mean().reset_index()
    
    # 4. 그래프 생성
    fig = go.Figure()
    colors = px.colors.qualitative.Plotly
    group_order = order_map.get(grouping_col, [])

    if xaxis_col == grouping_col:
        fig.add_trace(go.Bar(
            x=summary_df[xaxis_col],
            y=summary_df['WEEKEND_WORK_DAYS'],
            text=summary_df['WEEKEND_WORK_DAYS'].apply(lambda x: f'{x:.2f}' if pd.notna(x) else ''),
            textposition='outside'
        ))
    else:
        for i, group_name in enumerate(group_order):
            df_filtered = summary_df[summary_df[grouping_col] == group_name]
            if not df_filtered.empty:
                fig.add_trace(go.Bar(
                    x=df_filtered[xaxis_col],
                    y=df_filtered['WEEKEND_WORK_DAYS'],
                    name=str(group_name),
                    marker_color=colors[i % len(colors)],
                    text=df_filtered['WEEKEND_WORK_DAYS'].apply(lambda x: f'{x:.2f}' if pd.notna(x) else ''),
                    textposition='outside'
                ))

    # 5. 레이아웃 업데이트
    y_max = summary_df['WEEKEND_WORK_DAYS'].max() if not summary_df.empty else 0
    fixed_y_range = [0, y_max * 1.2 if y_max > 0 else 2]

    fig.update_layout(
        template='plotly',
        title_text=title_text,
        yaxis_title='월 평균 주말 근무일수 (일)',
        xaxis_title=dimension_ui_name,
        font_size=14,
        height=700,
        barmode='group',
        legend_title_text='직위',
        yaxis_range=fixed_y_range,
        xaxis=dict(categoryorder='array', categoryarray=xaxis_order)
    )
    
    # --- [수정된 부분 시작] ---
    # 6. 요약 테이블(aggregate_df) 생성
    pivot_col = config.get('top', config.get('col'))
    
    # X축과 그룹 축이 같은 경우, 단순 요약 테이블 생성
    if pivot_col == grouping_col:
        aggregate_df = analysis_df.groupby(grouping_col, observed=True)['WEEKEND_WORK_DAYS'].agg(['mean', 'count'])
        overall_avg = analysis_df['WEEKEND_WORK_DAYS'].mean()
        overall_count = len(analysis_df)
        aggregate_df.loc['전체 평균'] = [overall_avg, overall_count]
        aggregate_df = aggregate_df.rename(columns={'mean': '평균 주말 근무일수', 'count': '인원수'})
        
    # X축과 그룹 축이 다른 경우, 피벗 테이블 생성
    else:
        aggregate_df = analysis_df.pivot_table(
            index=grouping_col,
            columns=pivot_col,
            values='WEEKEND_WORK_DAYS',
            aggfunc='mean',
            observed=True
        )
        aggregate_df['전체 평균'] = analysis_df.groupby(grouping_col, observed=True)['WEEKEND_WORK_DAYS'].mean()
        
        pivot_order = order_map.get(pivot_col, [])
        cols = ['전체 평균'] + [col for col in pivot_order if col in aggregate_df.columns]
        aggregate_df = aggregate_df[cols]

    aggregate_df = aggregate_df.reindex(group_order).round(2).fillna('-').T
    # --- [수정된 부분 끝] ---

    return fig, aggregate_df