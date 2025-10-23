import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

def create_figure_and_df(data_bundle, dimension_ui_name, drilldown_selection, dimension_config, order_map):
    """
    제안 10: 학력/경력과 초봉의 관계 분석
    그래프 내 자체 드롭다운을 통해 '학교 레벨'과 '전공 계열' 뷰를 전환합니다.
    (dimension_ui_name, drilldown_selection, dimension_config는 app.py와의 호환성을 위해 받지만, 이 함수 내에서는 사용되지 않습니다.)
    """
    # data_bundle에서 analysis_df 추출
    analysis_df = data_bundle.get("analysis_df", pd.DataFrame())
    
    # 1. 데이터 유효성 검사
    if analysis_df.empty or 'INITIAL_SALARY' not in analysis_df.columns:
        fig = go.Figure().update_layout(title_text="분석할 데이터가 없습니다.")
        return fig, pd.DataFrame()

    # 2. 분석 및 그래프에 필요한 순서 정보 정의
    group_order = ['신입 (0~3년)', '주니어 (3~7년)', '시니어 (7년+)']
    
    school_level_order = sorted(pd.to_numeric(analysis_df['SCHOOL_LEVEL'].unique()))
    major_order = [
        "상경계열", "사회과학계열", "인문계열", "어문계열", "STEM계열",
        "기타공학계열", "자연과학계열", "디자인계열", "기타"
    ]
    
    # 3. 그래프 생성 및 모든 트레이스 추가
    fig = go.Figure()
    colors = px.colors.qualitative.Plotly

    # 3-1. '학교 레벨별' 트레이스 추가 (기본으로 보임)
    for i, group_name in enumerate(group_order):
        df_filtered = analysis_df[analysis_df['CAREER_BIN'] == group_name]
        fig.add_trace(go.Box(
            x=df_filtered['SCHOOL_LEVEL'], y=df_filtered['INITIAL_SALARY'],
            name=str(group_name), marker_color=colors[i % len(colors)],
            boxpoints='outliers', visible=True
        ))
        
    # 3-2. '전공 계열별' 트레이스 추가 (기본으로 숨김)
    for i, group_name in enumerate(group_order):
        df_filtered = analysis_df[analysis_df['CAREER_BIN'] == group_name]
        fig.add_trace(go.Box(
            x=df_filtered['MAJOR_CATEGORY'], y=df_filtered['INITIAL_SALARY'],
            name=str(group_name), marker_color=colors[i % len(colors)],
            boxpoints='outliers', visible=False
        ))

    # 4. 드롭다운 버튼 생성
    num_career_bins = len(group_order)
    buttons = [
        dict(label='학교 레벨별',
             method='update',
             args=[
                 {'visible': [True]*num_career_bins + [False]*num_career_bins},
                 {'xaxis': {'title': '학교 레벨', 'categoryorder': 'array', 'categoryarray': school_level_order}}
             ]),
        dict(label='전공 계열별',
             method='update',
             args=[
                 {'visible': [False]*num_career_bins + [True]*num_career_bins},
                 {'xaxis': {'title': '전공 계열', 'categoryorder': 'array', 'categoryarray': major_order}}
             ])
    ]
    
    # 5. 레이아웃 업데이트
    y_max = analysis_df['INITIAL_SALARY'].max() if not analysis_df['INITIAL_SALARY'].empty else 100000000
    fixed_y_range = [0, y_max * 1.1]

    fig.update_layout(
        template='plotly',
        updatemenus=[dict(
            active=0, buttons=buttons, direction="down",
            pad={"r": 10, "t": 10}, showactive=True,
            x=0.01, xanchor="left", y=1.1, yanchor="top"
        )],
        title_text='학력/경력과 초봉 관계 분석',
        xaxis_title='학교 레벨', # 초기 X축 제목
        yaxis_title='초봉 (연봉)',
        font_size=14, height=700,
        boxmode='group',
        legend_title_text='과거 경력',
        yaxis_range=fixed_y_range,
        yaxis_tickformat=',.0f',
        annotations=[dict(text="비교 기준:", showarrow=False, x=0, y=1.08, yref="paper", align="left")],
        xaxis=dict(categoryorder='array', categoryarray=school_level_order) # 초기 X축 순서
    )
    
    # 6. 요약 테이블(aggregate_df) 생성 (멀티인덱스 적용)
    aggregate_df = analysis_df.pivot_table(
        index=['SCHOOL_LEVEL', 'MAJOR_CATEGORY'], # 멀티인덱스로 변경
        columns='CAREER_BIN',
        values='INITIAL_SALARY',
        aggfunc='mean',
        observed=True
    )
    
    # 전체 평균 추가 (경력 무관)
    overall_avg = analysis_df.groupby(['SCHOOL_LEVEL', 'MAJOR_CATEGORY'], observed=True)['INITIAL_SALARY'].mean()
    aggregate_df['전체 평균'] = overall_avg
    
    # 컬럼 및 행 순서 재배치
    cols = ['전체 평균'] + [col for col in group_order if col in aggregate_df.columns]
    aggregate_df = aggregate_df[cols]
    
    # 멀티인덱스 순서 정렬
    aggregate_df = aggregate_df.reindex(pd.MultiIndex.from_product([school_level_order, major_order], names=['SCHOOL_LEVEL', 'MAJOR_CATEGORY']))
    aggregate_df = aggregate_df.round(-1).fillna('-')
    
    return fig, aggregate_df