import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from pandas.api.types import is_categorical_dtype

def create_figure_and_df(data_bundle, dimension_ui_name, drilldown_selection, dimension_config, order_map):
    """
    제안 4: 조직 경험 자산 현황 그래프 및 피벗 테이블을 생성합니다.
    aggregate_df가 drilldown_selection을 올바르게 반영하도록 수정되었습니다.
    """
    # data_bundle에서 analysis_df 추출
    analysis_df = data_bundle.get("analysis_df", pd.DataFrame())
    
    # 1. 데이터 및 설정 유효성 검사
    if analysis_df.empty or analysis_df['TENURE_YEARS'].isnull().all():
        fig = go.Figure().update_layout(title_text="분석할 데이터가 없습니다.")
        return fig, pd.DataFrame()

    config = dimension_config.get(dimension_ui_name)
    if not config:
        fig = go.Figure().update_layout(title_text=f"'{dimension_ui_name}'에 대한 설정이 없습니다.")
        return fig, pd.DataFrame()

    # --- 2. 동적 그룹핑 및 제목 설정 ---
    max_tenure = int(analysis_df['TENURE_YEARS'].max()) if not analysis_df['TENURE_YEARS'].empty else 0
    analysis_df = analysis_df.copy() # SettingWithCopyWarning 방지
    analysis_df['TENURE_BIN'] = pd.cut(
        analysis_df['TENURE_YEARS'],
        bins=range(0, max_tenure + 2),
        right=False,
        labels=range(0, max_tenure + 1)
    )
    
    # 설정(config)에 따라 동적으로 그룹핑 컬럼과 제목 결정
    if config['type'] == 'hierarchical' and drilldown_selection != '전체':
        top_level_col = config['top']
        grouping_col = config['sub']
        plot_df = analysis_df[analysis_df[top_level_col] == drilldown_selection].copy()
        if is_categorical_dtype(plot_df[grouping_col]):
            plot_df[grouping_col] = plot_df[grouping_col].cat.remove_unused_categories()
            
        category_order = [o for o in order_map.get(grouping_col, []) if o in plot_df[grouping_col].unique()]
        title_text = f"'{drilldown_selection}' 내 하위 그룹별 근속년수 분포"
    else:
        plot_df = analysis_df.copy()
        grouping_col = config.get('top', config.get('col'))
        category_order = order_map.get(grouping_col, [])
        title_text = f"{dimension_ui_name} 근속년수 분포"

    # 현재 뷰에 데이터가 없으면 빈 그래프 반환
    if plot_df.empty:
        fig = go.Figure().update_layout(title_text="선택된 조건에 해당하는 데이터가 없습니다.")
        return fig, pd.DataFrame()
        
    summary_df = plot_df.groupby([grouping_col, 'TENURE_BIN'], observed=False).size().reset_index(name='COUNT')

    # --- 3. Plotly 그래프 생성 ---
    fig = go.Figure()
    colors = px.colors.qualitative.Plotly

    for i, category_name in enumerate(category_order):
        if category_name not in summary_df[grouping_col].unique(): continue
        df_filtered = summary_df[summary_df[grouping_col] == category_name]
        fig.add_trace(go.Bar(
            x=df_filtered['TENURE_BIN'],
            y=df_filtered['COUNT'],
            name=category_name,
            marker_color=colors[i % len(colors)]
        ))

    fig.update_layout(
        title_text=title_text,
        xaxis_title='근속년수 (년)', yaxis_title='직원 수',
        font_size=14, height=700,
        bargap=0.2, barmode='stack', legend_title_text=dimension_ui_name,
        xaxis_range=[-0.5, max_tenure + 1.5]
    )
    fig.update_xaxes(dtick=1)

   # 4. 요약 테이블(aggregate_df) 생성
    table_df = plot_df.copy() # 원본 analysis_df 대신, 필터링된 plot_df 사용
    
    tenure_bins_agg = [-np.inf, 3, 7, np.inf]
    tenure_labels_agg = ['3년 이하', '3년초과~7년이하', '7년 초과']
    table_df['TENURE_GROUP'] = pd.cut(table_df['TENURE_YEARS'], bins=tenure_bins_agg, labels=tenure_labels_agg)

    aggregate_df = pd.pivot_table(
        table_df,
        index='TENURE_GROUP',
        columns=grouping_col, 
        values='EMP_ID',
        aggfunc='count',
        margins=True,
        margins_name='합계',
        observed=False
    ).fillna(0).astype(int)
    
    if '합계' in aggregate_df.columns:
        # category_order는 2번 단계에서 이미 뷰에 맞게 필터링됨
        cols_ordered = ['합계'] + [col for col in category_order if col in aggregate_df.columns and col != '합계']
        
        if config['type'] == 'hierarchical' and drilldown_selection != '전체':
            # 드릴다운 뷰에서는 category_order에 있는 것만 정확히 보여줌
            aggregate_df = aggregate_df[cols_ordered]
        else:
            # 최상위 뷰에서는 정의되지 않은 나머지 컬럼도 뒤에 붙여줌
            remaining_cols = [col for col in aggregate_df.columns if col not in cols_ordered]
            aggregate_df = aggregate_df[cols_ordered + remaining_cols]
    
    aggregate_df = aggregate_df.T
    
    return fig, aggregate_df