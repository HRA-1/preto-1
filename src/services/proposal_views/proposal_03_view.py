import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

def create_figure_and_df(data_bundle, dimension_ui_name, drilldown_selection, dimension_config, order_map):
    """
    제안 3: 조직 세대교체 현황 그래프 및 피벗 테이블을 생성합니다.
    선택된 차원에 따라 연령 분포를 바이올린 플롯으로 시각화합니다.
    """
    # data_bundle에서 analysis_df 추출
    analysis_df = data_bundle.get("analysis_df", pd.DataFrame())
    
    # 1. 데이터가 없는 경우 즉시 빈 결과 반환
    if analysis_df.empty:
        fig = go.Figure().update_layout(title_text="분석할 데이터가 없습니다.")
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
        plot_df = analysis_df[analysis_df[top_level_col] == drilldown_selection].copy()
        # 해당 드릴다운 선택지 내에 존재하는 카테고리만 순서를 적용
        unique_categories = plot_df[xaxis_col].unique()
        xaxis_order = [o for o in order_map.get(xaxis_col, []) if o in unique_categories]
        title_text = f"'{drilldown_selection}' 내 하위 그룹별 연령 분포"
    else:
        # 전체 뷰 (예: Division별 또는 성별)
        plot_df = analysis_df.copy()
        xaxis_col = config.get('top', config.get('col')) # 계층형 top 또는 단일형 col

        # "전체" 필터인 경우 (xaxis_col is None)
        if xaxis_col is None:
            xaxis_order = []
            title_text = "전체 연령 분포"
        else:
            xaxis_order = order_map.get(xaxis_col, [])
            title_text = f"{dimension_ui_name} 연령 분포"

    # 데이터가 없으면 빈 그래프 반환
    if plot_df.empty:
        fig = go.Figure().update_layout(title_text="선택된 조건에 해당하는 데이터가 없습니다.")
        return fig, pd.DataFrame()

    # 3. 그래프 생성 (Violin Plot)
    fig = go.Figure()

    if xaxis_col is None:
        # "전체" 필터: 차원별 그룹화 없이 전체 데이터로 단일 violin plot
        fig.add_trace(go.Violin(
            y=plot_df['AGE'],
            box_visible=True,
            meanline_visible=True,
            points='outliers',
            marker_color='royalblue',
            name='연령 분포'
        ))
    else:
        # 일반 필터: 차원별 그룹화된 violin plot
        # xaxis_order에 따라 데이터 순서 정렬
        plot_df[xaxis_col] = pd.Categorical(plot_df[xaxis_col], categories=xaxis_order, ordered=True)
        plot_df = plot_df.sort_values(xaxis_col)

        # 색상 맵 가져오기
        color_discrete_map = {category: color for category, color in zip(xaxis_order, px.colors.qualitative.Plotly)}

        fig.add_trace(go.Violin(
            x=plot_df[xaxis_col],
            y=plot_df['AGE'],
            box_visible=True,
            meanline_visible=True,
            points='outliers',
            marker_color='royalblue',
            name='연령 분포'
        ))

    layout_config = {
        'template': 'plotly',
        'title_text': title_text,
        'yaxis_title': '연령 (세)',
        'font_size': 14,
        'height': 700,
        'legend_title_text': '범례',
    }

    if xaxis_col is not None:
        layout_config['xaxis'] = dict(
            title=dimension_ui_name,
            categoryorder='array',
            categoryarray=xaxis_order
        )

    fig.update_layout(**layout_config)

    # 4. 요약 테이블(aggregate_df) 생성
    pivot_col = xaxis_col # 현재 보고 있는 X축 기준으로 요약

    if pivot_col is None:
        # "전체" 필터: 전체 평균만 표시
        aggregate_df = pd.DataFrame({
            '평균 연령': [analysis_df['AGE'].mean()],
            '중위 연령': [analysis_df['AGE'].median()],
            '최고령': [int(analysis_df['AGE'].max())],
            '최저령': [int(analysis_df['AGE'].min())],
            '인원수': [int(analysis_df['AGE'].count())]
        }, index=['전체 평균'])
        aggregate_df['평균 연령'] = aggregate_df['평균 연령'].round(1)
        aggregate_df['중위 연령'] = aggregate_df['중위 연령'].round(1)
    else:
        # 일반 필터: 차원별 평균 표시
        # 기술 통계량 계산
        agg_funcs = {
            '평균 연령': ('AGE', 'mean'),
            '중위 연령': ('AGE', 'median'),
            '최고령': ('AGE', 'max'),
            '최저령': ('AGE', 'min'),
            '인원수': ('AGE', 'count')
        }
        aggregate_df = plot_df.groupby(pivot_col, observed=False).agg(**agg_funcs).reset_index()

        # 전체 요약 행 추가
        total_summary = {
            pivot_col: '전체 평균',
            '평균 연령': analysis_df['AGE'].mean(),
            '중위 연령': analysis_df['AGE'].median(),
            '최고령': analysis_df['AGE'].max(),
            '최저령': analysis_df['AGE'].min(),
            '인원수': analysis_df['AGE'].count()
        }
        aggregate_df = pd.concat([aggregate_df, pd.DataFrame([total_summary])], ignore_index=True)

        # 컬럼 순서 설정 및 데이터 포맷팅
        aggregate_df = aggregate_df.set_index(pivot_col)

        # 정렬 순서에 맞게 인덱스 재정렬
        final_index_order = ['전체 평균'] + xaxis_order
        existing_indices = [idx for idx in final_index_order if idx in aggregate_df.index]
        aggregate_df = aggregate_df.reindex(existing_indices)

        # 숫자 포맷팅
        aggregate_df['평균 연령'] = aggregate_df['평균 연령'].round(1)
        aggregate_df['중위 연령'] = aggregate_df['중위 연령'].round(1)

        # .astype(int)를 적용하기 전에 .fillna(0)을 추가하여 NaN 값을 0으로 변환
        aggregate_df[['최고령', '최저령', '인원수']] = aggregate_df[['최고령', '최저령', '인원수']].fillna(0).astype(int)

    return fig, aggregate_df