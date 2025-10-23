import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from pandas.api.types import is_categorical_dtype

def create_figure_and_df(data_bundle, dimension_ui_name, drilldown_selection, dimension_config, order_map):
    """
    제안 18: 직원 번아웃 신호 감지 (연차-병가 사용 패턴 분석)
    2020년 이후 데이터만 필터링하며, 요약 테이블은 Transpose하여 반환합니다.
    (drilldown_selection은 app.py와의 호환성을 위해 받지만, 이 함수 내에서는 사용되지 않습니다.)
    """
    # data_bundle에서 analysis_df 추출
    analysis_df = data_bundle.get("analysis_df", pd.DataFrame())
    
    # --- [수정된 부분 1: 2020년 이후 데이터만 필터링] ---
    analysis_df = analysis_df[analysis_df['YEAR'] >= 2020].copy()
    
    # 1. 데이터 유효성 검사
    if analysis_df.empty or '연차휴가' not in analysis_df.columns or '병휴가' not in analysis_df.columns:
        fig = go.Figure().update_layout(title_text="분석할 데이터가 없습니다.")
        return fig, pd.DataFrame()

    config = dimension_config.get(dimension_ui_name, {})
    if not config:
        fig = go.Figure().update_layout(title_text=f"'{dimension_ui_name}'에 대한 설정이 없습니다.")
        return fig, pd.DataFrame()
    
    # 2. 분석 차원 및 순서 정의
    grouping_col = config.get('top', config.get('col'))
    group_order = order_map.get(grouping_col, sorted(analysis_df[grouping_col].unique()))
    
    available_years = sorted(analysis_df['YEAR'].unique(), reverse=True)
    if not available_years:
        fig = go.Figure().update_layout(title_text="분석할 연도 데이터가 없습니다.")
        return fig, pd.DataFrame()

    colors = px.colors.qualitative.Plotly
    fig = go.Figure()

    # 3. 각 연도별로, 각 그룹(예: Division, Job L1)별로 트레이스 추가
    trace_count_per_year = len(group_order)
    
    for year in available_years:
        df_year = analysis_df[analysis_df['YEAR'] == year]
        is_visible = (year == available_years[0])
        
        for i, group_name in enumerate(group_order):
            df_group = df_year[df_year[grouping_col] == group_name]
            if not df_group.empty:
                
                hovertemplate_str = (
                    f"<b>%{{customdata[0]}}</b> (ID: %{{customdata[1]}})<br>"
                    f"연차: %{{customdata[2]}}일<br>"
                    f"병가: %{{customdata[3]}}일<br>"
                    f"{dimension_ui_name}: %{{customdata[4]}}"
                    "<extra></extra>"
                )

                fig.add_trace(go.Scatter(
                    x=df_group['연차휴가_jitter'],
                    y=df_group['병휴가_jitter'],
                    mode='markers',
                    marker=dict(color=colors[i % len(colors)], size=10, opacity=0.7),
                    name=str(group_name),
                    legendgroup=str(group_name),
                    showlegend=bool(year == available_years[0]),
                    visible=is_visible,
                    hovertemplate=hovertemplate_str,
                    customdata=np.stack((
                        df_group['NAME'], 
                        df_group['EMP_ID'],
                        df_group['연차휴가'], 
                        df_group['병휴가'],
                        df_group[grouping_col]
                    ), axis=-1)
                ))

    # 4. 사분면 기준선 및 레이아웃 업데이트
    df_initial = analysis_df[analysis_df['YEAR'] == available_years[0]]
    x_median = df_initial['연차휴가'].median()
    y_median = df_initial['병휴가'].median()
    x_max = analysis_df['연차휴가'].max() * 1.1
    y_max = analysis_df['병휴가'].max() * 1.1

    fig.add_vline(x=x_median, line_width=1, line_dash="dash", line_color="grey")
    fig.add_hline(y=y_median, line_width=1, line_dash="dash", line_color="grey")
    
    annotations_list = [
        dict(x=0.02, y=0.98, xref="paper", yref="paper", text="번아웃 고위험군", showarrow=False, bgcolor="rgba(255, 255, 255, 0.5)"),
        dict(x=0.98, y=0.98, xref="paper", yref="paper", text="휴식 필요군", showarrow=False, bgcolor="rgba(255, 255, 255, 0.5)"),
        dict(x=0.02, y=0.02, xref="paper", yref="paper", text="업무 몰입형", showarrow=False, bgcolor="rgba(255, 255, 255, 0.5)"),
        dict(x=0.98, y=0.02, xref="paper", yref="paper", text="재충전형", showarrow=False, bgcolor="rgba(255, 255, 255, 0.5)")
    ]

    # 5. 드롭다운 버튼 생성
    buttons = []
    
    for i, year in enumerate(available_years):
        visibility_mask = [False] * len(fig.data)
        
        start_idx = i * trace_count_per_year
        end_idx = start_idx + trace_count_per_year
        visibility_mask[start_idx:end_idx] = [True] * trace_count_per_year
        
        df_year = analysis_df[analysis_df['YEAR'] == year]
        x_median_year = df_year['연차휴가'].median()
        y_median_year = df_year['병휴가'].median()
        
        buttons.append(dict(
            label=str(year),
            method='update',
            args=[
                {'visible': visibility_mask, 'showlegend': [bool((idx // trace_count_per_year) == i) for idx in range(len(fig.data))]},
                {'shapes': [
                    dict(type="line", x0=x_median_year, x1=x_median_year, y0=0, y1=y_max, line=dict(width=1, dash="dash", color="grey")),
                    dict(type="line", y0=y_median_year, y1=y_median_year, x0=0, x1=x_max, line=dict(width=1, dash="dash", color="grey"))
                ]}
            ]
        ))

    fig.update_layout(
        template='plotly',
        updatemenus=[dict(
            active=0, buttons=buttons, direction="down",
            pad={"r": 10, "t": 10}, showactive=True,
            x=0.01, xanchor="left", y=1.1, yanchor="top"
        )],
        title_text=f'연차-병가 사용 패턴 ({dimension_ui_name} 기준)',
        xaxis_title='연간 연차 사용일수 (일)',
        yaxis_title='연간 병가 사용일수 (일)',
        font_size=14, height=700,
        xaxis_range=[0, x_max], yaxis_range=[0, y_max],
        legend_title_text=dimension_ui_name,
        annotations=annotations_list + [dict(text="연도 선택:", showarrow=False, x=0, y=1.08, yref="paper", align="left")]
    )
    
    # 6. 요약 테이블(aggregate_df) 생성
    aggregate_df = analysis_df.groupby(['YEAR', grouping_col], observed=True)[['연차휴가', '병휴가']].mean()
    
    overall_avg = analysis_df.groupby('YEAR')[['연차휴가', '병휴가']].mean()
    overall_avg[grouping_col] = '전체'
    overall_avg = overall_avg.reset_index().set_index(['YEAR', grouping_col])
    
    aggregate_df = pd.concat([overall_avg, aggregate_df])
    
    aggregate_df = aggregate_df.unstack(level=grouping_col).round(1).fillna('-')
    
    cols_order = ['전체'] + [col for col in group_order if col in aggregate_df.columns.get_level_values(1)]
    aggregate_df = aggregate_df.reindex(columns=pd.MultiIndex.from_product([['연차휴가', '병휴가'], cols_order])).T

    return fig, aggregate_df