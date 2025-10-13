import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

def create_figure_and_df(analysis_df, order_map):
    """
    제안 8: 직무별 인력 유지 현황 분석 (재직자 vs 퇴사자)
    Y축에 '전체' 항목을 추가하여 시각화합니다.
    """
    # 1. 데이터 유효성 검사
    if analysis_df.empty or 'TENURE_YEARS' not in analysis_df.columns:
        fig = go.Figure().update_layout(title_text="분석할 데이터가 없습니다.")
        return fig, pd.DataFrame()

    # 2. 데이터 집계
    # 2-1. 직무(JOB_CATEGORY)별 평균 계산
    summary_by_job = analysis_df.groupby(['JOB_CATEGORY', 'STATUS'], observed=False).agg(
        AVG_TENURE=('TENURE_YEARS', 'mean'),
        HEADCOUNT=('EMP_ID', 'nunique')
    ).reset_index()

    # 2-2. '전체' 평균 계산
    summary_overall = analysis_df.groupby('STATUS', observed=False).agg(
        AVG_TENURE=('TENURE_YEARS', 'mean'),
        HEADCOUNT=('EMP_ID', 'nunique')
    ).reset_index()
    summary_overall['JOB_CATEGORY'] = '전체' # Y축 통일을 위해 컬럼 추가

    # 2-3. 데이터 합치기
    plot_df = pd.concat([summary_overall, summary_by_job], ignore_index=True)
    
    # 3. 그래프 생성
    fig = go.Figure()
    
    df_active = plot_df[plot_df['STATUS'] == '재직자']
    df_leaver = plot_df[plot_df['STATUS'] == '퇴사자']
    
    fig.add_trace(go.Bar(
        y=df_active['JOB_CATEGORY'], x=df_active['AVG_TENURE'], 
        name='재직자', orientation='h', marker_color='blue',
        text=df_active['AVG_TENURE'].round(2), textposition='outside',
        customdata=df_active['HEADCOUNT'],
        hovertemplate='평균 재직기간: %{x:.2f}년<br>인원: %{customdata}명<extra></extra>'
    ))
    fig.add_trace(go.Bar(
        y=df_leaver['JOB_CATEGORY'], x=df_leaver['AVG_TENURE'], 
        name='퇴사자', orientation='h', marker_color='red',
        text=df_leaver['AVG_TENURE'].round(2), textposition='outside',
        customdata=df_leaver['HEADCOUNT'],
        hovertemplate='평균 재직기간: %{x:.2f}년<br>인원: %{customdata}명<extra></extra>'
    ))

    # 4. 레이아웃 업데이트
    x_max = plot_df['AVG_TENURE'].max() if not plot_df.empty else 10
    fixed_x_range = [0, x_max * 1.2]
    
    # Y축 순서 정의: '전체'를 맨 위로
    job_l1_order = order_map.get('JOB_L1_NAME', [])
    yaxis_order = ['전체'] + job_l1_order

    fig.update_layout(
        template='plotly',
        title_text='직무별 평균 재직기간 비교 (재직자 vs 퇴사자)',
        xaxis_title='평균 재직 기간 (년)',
        font_size=14,
        height=700,
        barmode='group',
        legend_title_text='상태',
        xaxis_range=fixed_x_range,
        yaxis=dict(
            title='마지막 직무 대분류',
            categoryorder='array',
            categoryarray=yaxis_order[::-1] # 가로 막대그래프는 순서 반전
        )
    )
    
    # 5. 요약 테이블(aggregate_df) 생성
    aggregate_df = plot_df.pivot_table(
        index='JOB_CATEGORY',
        columns='STATUS',
        values='AVG_TENURE'
    ).round(2)
    
    # 순서에 맞게 재정렬
    aggregate_df = aggregate_df.reindex(yaxis_order)
    if '재직자' in aggregate_df.columns and '퇴사자' in aggregate_df.columns:
        aggregate_df = aggregate_df[['재직자', '퇴사자']] # 컬럼 순서 고정

    return fig, aggregate_df