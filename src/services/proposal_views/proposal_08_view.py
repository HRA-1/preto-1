import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from pandas.api.types import is_categorical_dtype

def create_figure_and_df(data_bundle, dimension_ui_name, drilldown_selection, dimension_config, order_map):
    """
    제안 8: 인력 유지 현황 분석 (재직자 vs 퇴사자) - 범용 버전
    dimension_config에 따라 동적으로 Y축을 변경하여 가로 막대그래프를 생성합니다.
    """
    # data_bundle에서 analysis_df 추출
    analysis_df = data_bundle.get("analysis_df", pd.DataFrame())

    # 1. 데이터 및 설정 유효성 검사
    if analysis_df.empty or 'TENURE_YEARS' not in analysis_df.columns:
        fig = go.Figure().update_layout(title_text="분석할 데이터가 없습니다.")
        return fig, pd.DataFrame()

    config = dimension_config.get(dimension_ui_name, {})
    if not config:
        fig = go.Figure().update_layout(title_text=f"'{dimension_ui_name}'에 대한 설정이 없습니다.")
        return fig, pd.DataFrame()

    # 2. 차원 설정에 따라 그래프용 데이터(plot_df) 및 Y축(yaxis_col) 설정
    if config.get('type') == 'hierarchical' and drilldown_selection != '전체':
        # 드릴다운 뷰 (예: 특정 Division 내 Office별)
        top_level_col = config.get('top')
        yaxis_col = config.get('sub')
        plot_df = analysis_df[analysis_df[top_level_col] == drilldown_selection].copy()
        
        # 드릴다운 시, 현재 뷰에 없는 카테고리 Y축에서 제거
        if is_categorical_dtype(plot_df[yaxis_col]):
            plot_df[yaxis_col] = plot_df[yaxis_col].cat.remove_unused_categories()
            
        yaxis_order = [o for o in order_map.get(yaxis_col, []) if o in plot_df[yaxis_col].unique()]
        title_text = f"'{drilldown_selection}' 내 하위 그룹별 인력 유지 현황"
    else:
        # 최상위 뷰 (예: Division별 또는 성별)
        plot_df = analysis_df.copy()
        yaxis_col = config.get('top', config.get('col'))
        yaxis_order = order_map.get(yaxis_col, sorted(plot_df[yaxis_col].unique()))
        title_text = f"{dimension_ui_name} 인력 유지 현황"

    if plot_df.empty:
        fig = go.Figure().update_layout(title_text=f"'{drilldown_selection}'에 해당하는 데이터가 없습니다.")
        return fig, pd.DataFrame()

    # 3. 데이터 집계
    # 3-1. 선택된 차원(yaxis_col)별 평균 계산
    summary_by_group = plot_df.groupby([yaxis_col, 'STATUS'], observed=False).agg(
        AVG_TENURE=('TENURE_YEARS', 'mean'),
        HEADCOUNT=('EMP_ID', 'nunique')
    ).reset_index()

    # 3-2. '전체' 평균 계산 (현재 뷰 기준)
    summary_overall = plot_df.groupby('STATUS', observed=False).agg(
        AVG_TENURE=('TENURE_YEARS', 'mean'),
        HEADCOUNT=('EMP_ID', 'nunique')
    ).reset_index()
    summary_overall[yaxis_col] = '전체' # Y축 통일을 위해 컬럼 추가

    # 3-3. 데이터 합치기
    plot_df_agg = pd.concat([summary_overall, summary_by_group], ignore_index=True)
    
    # 4. 그래프 생성
    fig = go.Figure()
    
    df_active = plot_df_agg[plot_df_agg['STATUS'] == '재직자']
    df_leaver = plot_df_agg[plot_df_agg['STATUS'] == '퇴사자']
    
    fig.add_trace(go.Bar(
        y=df_active[yaxis_col], x=df_active['AVG_TENURE'], 
        name='재직자', orientation='h', marker_color='blue',
        text=df_active['AVG_TENURE'].apply(lambda x: f'{x:.2f}' if pd.notna(x) else ''), # NaN 텍스트 제거
        textposition='outside',
        customdata=df_active['HEADCOUNT'],
        hovertemplate='평균 재직기간: %{x:.2f}년<br>인원: %{customdata}명<extra></extra>'
    ))
    fig.add_trace(go.Bar(
        y=df_leaver[yaxis_col], x=df_leaver['AVG_TENURE'], 
        name='퇴사자', orientation='h', marker_color='red',
        text=df_leaver['AVG_TENURE'].apply(lambda x: f'{x:.2f}' if pd.notna(x) else ''), # NaN 텍스트 제거
        textposition='outside',
        customdata=df_leaver['HEADCOUNT'],
        hovertemplate='평균 재직기간: %{x:.2f}년<br>인원: %{customdata}명<extra></extra>'
    ))

    # 5. 레이아웃 업데이트
    x_max = plot_df_agg['AVG_TENURE'].max() if not plot_df_agg.empty else 10
    fixed_x_range = [0, x_max * 1.25] # 텍스트 공간 확보
    
    # Y축 순서 정의: '전체'를 맨 위로
    yaxis_final_order = ['전체'] + yaxis_order

    fig.update_layout(
        template='plotly',
        title_text=title_text,
        xaxis_title='평균 재직 기간 (년)',
        font_size=14,
        height=700,
        barmode='group',
        legend_title_text='상태',
        xaxis_range=fixed_x_range,
        yaxis=dict(
            title=dimension_ui_name,
            categoryorder='array',
            categoryarray=yaxis_final_order[::-1] # 가로 막대그래프는 순서 반전
        )
    )
    
    # 6. 요약 테이블(aggregate_df) 생성
    aggregate_df = plot_df_agg.pivot_table(
        index=yaxis_col,
        columns='STATUS',
        values='AVG_TENURE'
    ).round(2)
    
    # 순서에 맞게 재정렬
    aggregate_df = aggregate_df.reindex(yaxis_final_order).fillna('-')
    if '재직자' in aggregate_df.columns and '퇴사자' in aggregate_df.columns:
        aggregate_df = aggregate_df[['재직자', '퇴사자']] # 컬럼 순서 고정

    return fig, aggregate_df