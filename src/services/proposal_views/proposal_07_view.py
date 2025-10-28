import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

def create_figure_and_df(data_bundle, dimension_ui_name, drilldown_selection, dimension_config, order_map):
    """
    제안 7: 경력 유형 및 첫 직무별 재직기간 분석 그래프 및 피벗 테이블을 생성합니다.
    (drilldown_selection, dimension_config는 app.py와의 호환성을 위해 받지만, 이 함수 내에서는 사용되지 않습니다.)
    """
    # data_bundle에서 analysis_df 추출
    analysis_df = data_bundle.get("analysis_df", pd.DataFrame())
    
    # 1. 데이터 유효성 검사
    if analysis_df.empty or 'TENURE_YEARS' not in analysis_df.columns:
        fig = go.Figure().update_layout(title_text="분석할 데이터가 없습니다.")
        return fig, pd.DataFrame()

    # 2. 분석 및 그래프에 필요한 순서 정보 정의
    xaxis_col = 'JOB_CATEGORY'
    grouping_col = 'CAREER_TYPE'
    
    xaxis_order = order_map.get(xaxis_col, sorted(analysis_df[xaxis_col].unique()))
    group_order = order_map.get(grouping_col, ['관련 경력', '비관련 경력', '경력 없음'])
    
    # 3. 그래프 생성 (그룹화된 박스 플롯)
    fig = go.Figure()
    colors = px.colors.qualitative.Plotly

    for i, group_name in enumerate(group_order):
        if group_name in analysis_df[grouping_col].unique():
            df_filtered = analysis_df[analysis_df[grouping_col] == group_name]
            fig.add_trace(go.Box(
                y=df_filtered['TENURE_YEARS'],
                x=df_filtered[xaxis_col],
                name=group_name,
                marker_color=colors[i % len(colors)],
                boxpoints='outliers'
            ))

    # 4. 레이아웃 업데이트
    y_max = analysis_df['TENURE_YEARS'].max() if not analysis_df['TENURE_YEARS'].empty else 10
    fixed_y_range = [0, y_max * 1.1]

    fig.update_layout(
        template='plotly',
        title_text=f'{dimension_ui_name} 필터 적용: 첫 직무 및 경력 유형별 재직기간',
        xaxis_title='첫 직무 대분류',
        yaxis_title='재직 기간 (년)',
        font_size=14,
        height=700,
        boxmode='group',
        legend_title_text='과거 경력 유형',
        yaxis_range=fixed_y_range,
        xaxis=dict(
            categoryorder='array',
            categoryarray=xaxis_order
        )
    )
    
    # 5. 요약 테이블(aggregate_df) 생성
    
    # UI 이름과 실제 컬럼명을 매핑하는 딕셔너리
    dim_map = {
        '부서별': 'DIVISION_NAME', '직무별': 'JOB_L1_NAME', '직위직급별': 'POSITION_NAME',
        '성별': 'GENDER', '연령별': 'AGE_BIN', '경력연차별': 'CAREER_BIN',
        '연봉구간별': 'SALARY_BIN', '지역별': 'REGION_CATEGORY', '계약별': 'CONT_CATEGORY'
    }
    pivot_col = dim_map.get(dimension_ui_name)
    
    if pivot_col and pivot_col in analysis_df.columns:
        aggregate_df = analysis_df.pivot_table(
            index=['JOB_CATEGORY', 'CAREER_TYPE'],
            columns=pivot_col,
            values='TENURE_YEARS',
            aggfunc='mean',
            observed=True
        )
        overall_avg = analysis_df.groupby(['JOB_CATEGORY', 'CAREER_TYPE'], observed=True)['TENURE_YEARS'].mean()
        aggregate_df['전체 평균'] = overall_avg
        
        pivot_order = order_map.get(pivot_col, [])
        cols = ['전체 평균'] + [col for col in pivot_order if col in aggregate_df.columns]
        aggregate_df = aggregate_df[cols]
        
        aggregate_df = aggregate_df.reindex(pd.MultiIndex.from_product([xaxis_order, group_order], names=['JOB_CATEGORY', 'CAREER_TYPE']))
        aggregate_df = aggregate_df.round(2).fillna('-')
    else:
        # '전체'가 선택되었거나, 매핑되는 컬럼이 없는 경우, 기본 요약 테이블 생성
        aggregate_df = analysis_df.groupby(['JOB_CATEGORY', 'CAREER_TYPE'], observed=True)['TENURE_YEARS'].agg(['mean', 'count']).round(2)
    
    aggregate_df = aggregate_df.T

    return fig, aggregate_df