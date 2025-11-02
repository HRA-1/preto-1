import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from pandas.api.types import is_categorical_dtype

def create_figure_and_df(data_bundle, dimension_ui_name, drilldown_selection, dimension_config, order_map):
    """
    제안 14: 조직별/직위별 지각률(%) 분석
    dimension_config에 따라 동적으로 X축을 변경하여 그룹화된 막대그래프를 생성합니다.
    """
    # data_bundle에서 analysis_df 추출
    analysis_df = data_bundle.get("analysis_df", pd.DataFrame())

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
        plot_df = analysis_df[analysis_df[top_level_col] == drilldown_selection].copy()
        if is_categorical_dtype(plot_df[xaxis_col]):
            plot_df[xaxis_col] = plot_df[xaxis_col].cat.remove_unused_categories()
        xaxis_order = [o for o in order_map.get(xaxis_col, []) if o in plot_df[xaxis_col].unique()]
        title_text = f"'{drilldown_selection}' 내 하위 그룹별/직위별 지각률"
    else:
        # 최상위 뷰
        plot_df = analysis_df
        xaxis_col = config.get('top', config.get('col'))

        # "전체" 필터인 경우 (xaxis_col is None)
        if xaxis_col is None:
            xaxis_order = []
            title_text = "전체 직위별 지각률"
        else:
            xaxis_order = order_map.get(xaxis_col, sorted(plot_df[xaxis_col].unique()))
            title_text = f"{dimension_ui_name} 구분에 대한 직위별 지각률"

    if plot_df.empty:
        fig = go.Figure().update_layout(title_text=f"'{drilldown_selection}'에 해당하는 데이터가 없습니다.")
        return fig, pd.DataFrame()

    # --- [수정된 부분 1: groupby 오류 해결] ---
    # 3. 지각률 계산
    if xaxis_col == grouping_col:
        # X축과 그룹 축이 같으면, X축으로만 그룹핑
        summary_df = plot_df.groupby(xaxis_col, observed=False)['IS_LATE'].mean().reset_index()
        summary_df['LATENESS_RATE'] = summary_df['IS_LATE'] * 100
    else:
        # X축과 그룹 축이 다르면, 두 축 모두로 그룹핑
        total_days = plot_df.groupby([xaxis_col, grouping_col], observed=False).size().reset_index(name='TOTAL_DAYS')
        late_days = plot_df[plot_df['IS_LATE']].groupby([xaxis_col, grouping_col], observed=False).size().reset_index(name='LATE_DAYS')
        lateness_df = pd.merge(total_days, late_days, on=[xaxis_col, grouping_col], how='left')
        lateness_df['LATE_DAYS'] = lateness_df['LATE_DAYS'].fillna(0)
        lateness_df['LATENESS_RATE'] = (lateness_df['LATE_DAYS'] / lateness_df['TOTAL_DAYS'] * 100).fillna(0)
        summary_df = lateness_df
        
    # 4. 그래프 생성
    fig = go.Figure()
    colors = px.colors.qualitative.Plotly
    group_order = order_map.get(grouping_col, [])

    if xaxis_col == grouping_col:
        # X축과 그룹 축이 같으면, 그룹 없이 단일 막대 그래프를 그림
        fig.add_trace(go.Bar(
            x=summary_df[xaxis_col],
            y=summary_df['LATENESS_RATE'],
            text=summary_df['LATENESS_RATE'].apply(lambda x: f'{x:.1f}%' if pd.notna(x) else ''),
            textposition='outside'
        ))
    else:
        # X축과 그룹 축이 다르면, 그룹화된 막대 그래프를 그림
        for i, group_name in enumerate(group_order):
            df_filtered = summary_df[summary_df[grouping_col] == group_name]
            if not df_filtered.empty:
                fig.add_trace(go.Bar(
                    x=df_filtered[xaxis_col],
                    y=df_filtered['LATENESS_RATE'],
                    name=str(group_name),
                    marker_color=colors[i % len(colors)],
                    text=df_filtered['LATENESS_RATE'].apply(lambda x: f'{x:.1f}%' if pd.notna(x) else ''),
                    textposition='outside'
                ))

    # 5. 레이아웃 업데이트
    y_max = summary_df['LATENESS_RATE'].max() if not summary_df.empty else 0
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
    
    if pivot_col == grouping_col:
        # X축과 그룹 축이 같은 경우, 단순 요약 테이블 생성
        total_days_agg = analysis_df.groupby(grouping_col, observed=False).size().rename('TOTAL_DAYS')
        late_days_agg = analysis_df[analysis_df['IS_LATE']].groupby(grouping_col, observed=False).size().rename('LATE_DAYS')
        aggregate_df = pd.concat([total_days_agg, late_days_agg], axis=1).fillna(0)
        aggregate_df['지각률 (%)'] = (aggregate_df['LATE_DAYS'] / aggregate_df['TOTAL_DAYS'] * 100).fillna(0)
        
        total_days_overall = len(analysis_df)
        late_days_overall = len(analysis_df[analysis_df['IS_LATE']])
        overall_rate = (late_days_overall / total_days_overall * 100) if total_days_overall > 0 else 0
        aggregate_df.loc['전체 평균'] = [total_days_overall, late_days_overall, overall_rate]
        
        aggregate_df['지각률 (%)'] = aggregate_df['지각률 (%)'].apply(lambda x: f"{x:.2f}%").replace("0.00%", "-").replace("nan%", "-")
        aggregate_df[['TOTAL_DAYS', 'LATE_DAYS']] = aggregate_df[['TOTAL_DAYS', 'LATE_DAYS']].astype(int)

    else:
        # X축과 그룹 축이 다른 경우, 피벗 테이블 생성
        total_days_agg = analysis_df.groupby([pivot_col, grouping_col], observed=False).size()
        late_days_agg = analysis_df[analysis_df['IS_LATE']].groupby([pivot_col, grouping_col], observed=False).size()
        
        lateness_rate_agg = (late_days_agg / total_days_agg * 100).unstack(level=pivot_col).fillna(0)
        
        total_days_overall = analysis_df.groupby(grouping_col, observed=False).size()
        late_days_overall = analysis_df[analysis_df['IS_LATE']].groupby(grouping_col, observed=False).size()
        lateness_rate_overall = (late_days_overall / total_days_overall * 100).fillna(0)
        lateness_rate_agg['전체 평균'] = lateness_rate_overall
        
        pivot_order = order_map.get(pivot_col, [])
        cols = ['전체 평균'] + [col for col in pivot_order if col in lateness_rate_agg.columns]
        aggregate_df = lateness_rate_agg[cols]
        aggregate_df = aggregate_df.reindex(group_order).applymap(lambda x: f"{x:.2f}%").replace("0.00%", "-").replace("nan%", "-").T
    # --- [수정된 부분 끝] ---

    return fig, aggregate_df