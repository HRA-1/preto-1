import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def create_figure_and_df(data_bundle, dimension_ui_name, period_agg_name):
    """
    제안 0: 기본 인원 변동 현황 그래프 및 요약 테이블을 생성합니다.
    - data_bundle: prepare_basic_proposal_data()가 반환한 데이터 묶음
    - dimension_ui_name: 사용자가 선택한 분석 차원 (예: '부서별', '직무별')
    - period_agg_name: 사용자가 선택한 기간 단위 (예: 'quarterly', 'monthly')
    """
    # 1. 전달받은 인자에 따라 분석할 데이터프레임 선택
    dimension_data = data_bundle.get(dimension_ui_name, data_bundle['전체'])
    summary_df = dimension_data.get(period_agg_name)
    overall_summary_df = data_bundle['전체'].get(period_agg_name)

    if summary_df is None or summary_df.empty:
        fig = go.Figure().update_layout(title_text=f"{dimension_ui_name}에 대한 데이터가 없습니다.")
        return fig, pd.DataFrame()

    # 2. 분석 차원에 따른 컬럼명 및 하위 그룹 목록 설정
    dim_map = {
        '부서별': 'DIVISION_NAME', '직무별': 'JOB_L1_NAME', '직위직급별': 'POSITION_NAME',
        '성별': 'GENDER', '연령별': 'AGE_BIN', '경력연차별': 'CAREER_BIN',
        '연봉구간별': 'SALARY_BIN', '지역별': 'REGION_CATEGORY', '계약별': 'CONT_CATEGORY'
    }
    dimension_col = dim_map.get(dimension_ui_name)
    
    subgroups = ['전체']
    if dimension_col and dimension_col in summary_df.columns:
        subgroups += sorted(summary_df[dimension_col].unique())

    # 기간(PERIOD) 컬럼 생성
    period_map = {'monthly': ('PERIOD_DT', '%Y년 %m월'), 'quarterly': ('QUARTER', '분기')}
    period_source_col, period_format = period_map.get(period_agg_name, ('PERIOD_DT', None))
    
    for df in [summary_df, overall_summary_df]:
        if period_source_col in df.columns:
            if period_format == '분기':
                df['PERIOD'] = df[period_source_col].apply(lambda q: f"{q.year}년 {q.quarter}분기")
            else:
                df['PERIOD'] = df[period_source_col].dt.strftime(period_format)

    # 3. Plotly 그래프 생성
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    trace_map = {'전체': overall_summary_df.tail(12)}
    if dimension_col:
        for group_name in subgroups:
            if group_name != '전체':
                trace_map[group_name] = summary_df[summary_df[dimension_col] == group_name].tail(12)

    for name in subgroups:
        df_plot = trace_map.get(name)
        if df_plot is None or df_plot.empty: continue
        
        is_visible = (name == '전체')
        
        fig.add_trace(go.Bar(x=df_plot['PERIOD'], y=df_plot['NEW_HIRES'], name='입사자', marker_color='blue', visible=is_visible, legendgroup='hires'), secondary_y=False)
        fig.add_trace(go.Bar(x=df_plot['PERIOD'], y=df_plot['LEAVERS'], name='퇴사자', marker_color='red', visible=is_visible, legendgroup='leavers'), secondary_y=False)
        fig.add_trace(go.Scatter(x=df_plot['PERIOD'], y=df_plot['HEADCOUNT'], name='총원', mode='lines+markers+text', text=df_plot['HEADCOUNT'], textposition='top center', line=dict(color='black'), visible=is_visible, legendgroup='headcount'), secondary_y=True)

    # 4. 드롭다운 메뉴 및 레이아웃 업데이트
    buttons = []
    num_traces_per_group = 3
    for i, name in enumerate(subgroups):
        visibility_mask = [False] * (len(subgroups) * num_traces_per_group)
        start_idx = i * num_traces_per_group
        
        visibility_mask[start_idx : start_idx + num_traces_per_group] = [True] * num_traces_per_group
            
        df_for_range = trace_map.get(name, pd.DataFrame())
        max_val = 0
        if not df_for_range.empty:
            max_val = max(df_for_range['NEW_HIRES'].max(), df_for_range['LEAVERS'].max())
        
        y1_range = [0, max_val * 2.2 if max_val > 0 else 10]

        buttons.append(dict(label=name, method='update', args=[
            {'visible': visibility_mask},
            {'yaxis.range': y1_range}
        ]))
        
    initial_df = trace_map['전체']
    initial_max = max(initial_df['NEW_HIRES'].max(), initial_df['LEAVERS'].max()) if not initial_df.empty else 10
    initial_y1_range = [0, initial_max * 2.2 if initial_max > 0 else 10]
    
    period_name_kor = "월별" if period_agg_name == "monthly" else "분기별"
    title_text = f'{dimension_ui_name} {period_name_kor} 인원 변동 현황'
    if dimension_ui_name == '전체':
        title_text = f'{period_name_kor} 인원 변동 현황'

    fig.update_layout(
        updatemenus=[dict(
            active=0, buttons=buttons, direction="down",
            pad={"r": 10, "t": 10}, showactive=True,
            x=0.01, xanchor="left", y=1.1, yanchor="top"
        )],
        title_text=title_text,
        xaxis_title='기간', font_size=14, height=700,
        barmode='group',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, tracegroupgap=20),
        annotations=[dict(text=f"{dimension_ui_name} 선택:", showarrow=False, x=0, y=1.08, yref="paper", align="left")]
    )
    fig.update_yaxes(title_text="입사/퇴사자 수", secondary_y=False, range=initial_y1_range)
    fig.update_yaxes(title_text="총원", secondary_y=True, rangemode='tozero')
    
    # 5. 요약 테이블(aggregate_df) 생성
    aggregate_df = pd.DataFrame()
    if dimension_col:
        pivot_df = summary_df.copy()
        pivot_df['PERIOD'] = pivot_df[period_source_col].astype(str)
        
        aggregate_df = pivot_df.pivot_table(
            index='PERIOD', 
            columns=dimension_col, 
            values='HEADCOUNT',
            aggfunc='last'
        ).fillna(0).astype(int)

        overall_agg = overall_summary_df.set_index('PERIOD')['HEADCOUNT']
        aggregate_df['전체'] = overall_agg
        aggregate_df = aggregate_df[['전체'] + [col for col in aggregate_df.columns if col != '전체']]
        aggregate_df = aggregate_df.tail(12)

    return fig, aggregate_df