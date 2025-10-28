import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

def create_figure_and_df(data_bundle, dimension_ui_name, drilldown_selection, dimension_config, order_map):
    """
    제안 19: 퇴사 예측 선행 지표 분석 (단순화 및 드릴다운 버전)
    선택된 그룹(전체 또는 하위 그룹)의 퇴사자/재직자 패턴만 비교합니다.
    """
    # 1. 데이터 및 설정 유효성 검사
    leavers_df = data_bundle.get("leavers_df")
    stayers_df = data_bundle.get("stayers_df")

    if leavers_df is None or leavers_df.empty or stayers_df is None or stayers_df.empty:
        fig = go.Figure().update_layout(title_text="분석할 데이터가 없습니다.")
        return fig, pd.DataFrame()

    config = dimension_config.get(dimension_ui_name, {})
    if not config:
        fig = go.Figure().update_layout(title_text=f"'{dimension_ui_name}'에 대한 설정이 없습니다.")
        return fig, pd.DataFrame()

    # --- [수정된 부분 1: 퇴사 0개월 전 데이터 제외] ---
    leavers_df = leavers_df[leavers_df['MONTHS_BEFORE_LEAVING'] >= 1].copy()

    # 2. 사용자 선택에 따라 그릴 데이터(plot_df)와 속성 결정
    if drilldown_selection == '전체':
        plot_leavers = leavers_df[leavers_df['GROUP_TYPE'] == '전체']
        plot_stayers = stayers_df[stayers_df['GROUP_TYPE'] == '전체']
        title_text = "전체 그룹 퇴사자 휴가 사용 패턴"
    else:
        grouping_col_name = config.get('top', config.get('col'))
        plot_leavers = leavers_df[
            (leavers_df['GROUP_TYPE'] == grouping_col_name) & 
            (leavers_df['GROUP_NAME'] == drilldown_selection)
        ]
        plot_stayers = stayers_df[
            (stayers_df['GROUP_TYPE'] == grouping_col_name) & 
            (stayers_df['GROUP_NAME'] == drilldown_selection)
        ]
        title_text = f"'{drilldown_selection}' 그룹 퇴사자 휴가 사용 패턴"

    # 3. Plotly 그래프 생성
    fig = go.Figure()
    
    if plot_leavers.empty or plot_stayers.empty:
        fig.update_layout(title_text=f"'{drilldown_selection}' 그룹의 데이터가 없습니다.")
        return fig, pd.DataFrame()

    baseline_value = plot_stayers['BASELINE_LEAVE_DAYS'].iloc[0]

    # '퇴사자' 꺾은선 그래프 추가
    fig.add_trace(go.Scatter(
        x=plot_leavers['MONTHS_BEFORE_LEAVING'], 
        y=plot_leavers['LEAVE_DAYS_AVG'], 
        name=f'{drilldown_selection} (퇴사자)',
        mode='lines+markers+text',
        text=plot_leavers['LEAVE_DAYS_AVG'].round(1),
        textposition='top center',
        line=dict(color='red', width=4)
    ))
    
    # '재직자' 기준선 추가
    fig.add_hline(
        y=baseline_value, 
        line_width=2, line_dash="dash", line_color="blue",
        name=f'{drilldown_selection} (재직자 평균)', 
        annotation_text=f"{drilldown_selection} 재직자 평균: {baseline_value:.2f}일", 
        annotation_position="bottom right"
    )

    # 4. 레이아웃 업데이트
    y_max = plot_leavers['LEAVE_DAYS_AVG'].max()
    fixed_y_range = [0, max(y_max, baseline_value) * 1.2 if not pd.isna(y_max) else 5]

    fig.update_layout(
        template='plotly',
        title_text=title_text,
        xaxis_title='퇴사 N개월 전',
        yaxis_title='월평균 휴가 사용일수 (일)',
        font_size=14,
        height=700,
        legend_title_text='범례',
        yaxis_range=fixed_y_range,
        xaxis = dict(
            tickmode = 'linear',
            tick0 = 1, # 1개월 전부터 시작
            dtick = 1,
            autorange = "reversed" # X축 순서 반대로 (1이 가장 오른쪽)
        )
    )
    
    # 5. 요약 테이블(aggregate_df) 생성
    
    # 5-1. 피벗 테이블 생성 (행: 퇴사 N개월 전, 열: 각 그룹)
    pivot_col = config.get('top', config.get('col'))
    pivot_order = order_map.get(pivot_col, [])
    
    leavers_pivot_data = leavers_df[leavers_df['GROUP_TYPE'] == pivot_col]
    aggregate_df = leavers_pivot_data.pivot_table(
        index='MONTHS_BEFORE_LEAVING', 
        columns='GROUP_NAME', 
        values='LEAVE_DAYS_AVG'
    )
    
    # 5-2. '전체' (퇴사자) 열 추가
    overall_leavers_data = leavers_df[leavers_df['GROUP_TYPE'] == '전체']
    aggregate_df['전체'] = overall_leavers_data.set_index('MONTHS_BEFORE_LEAVING')['LEAVE_DAYS_AVG']
    
    # 5-3. '재직자 월평균' 행 추가
    stayers_data = stayers_df[stayers_df['GROUP_TYPE'] == pivot_col]
    stayers_row_data = stayers_data.set_index('GROUP_NAME')['BASELINE_LEAVE_DAYS']
    
    overall_stayer_baseline = stayers_df[stayers_df['GROUP_TYPE'] == '전체']['BASELINE_LEAVE_DAYS'].iloc[0]
    stayers_row_data['전체'] = overall_stayer_baseline
    stayers_row_data.name = '재직자 월평균'
    
    # 5-4. 데이터 합치기 및 정렬
    stayers_df_agg = pd.DataFrame(stayers_row_data).transpose()
    aggregate_df = pd.concat([aggregate_df, stayers_df_agg])
    
    # 컬럼 순서 정렬
    cols_ordered = ['전체'] + [col for col in pivot_order if col in aggregate_df.columns]
    aggregate_df = aggregate_df[cols_ordered]
    
    # 인덱스(행) 이름 변경 및 순서 정렬
    # '재직자 월평균'을 제외한 숫자 인덱스만 'N개월 전'으로 변경
    new_index_map = {idx: f"{idx}개월 전" for idx in aggregate_df.index if isinstance(idx, (int, float))}
    aggregate_df = aggregate_df.rename(index=new_index_map)
    
    # 정렬 키 함수: 'N개월 전'에서 숫자 N을 추출
    def get_month_num(index_str):
        if "개월 전" in index_str:
            return int(index_str.split("개월 전")[0])
        return np.inf # '재직자 월평균'을 맨 뒤로 보내기 위함
    
    # '재직자 월평균'을 제외한 인덱스를 숫자로 변환하여 정렬
    numeric_indices_sorted = sorted(
        [idx for idx in aggregate_df.index if idx != '재직자 월평균'], 
        key=get_month_num, 
        reverse=False # 1개월 전, 2개월 전... 순서
    )
    
    # 사용자가 제공한 순서로 최종 reindex
    index_order = ['재직자 월평균'] + numeric_indices_sorted
    aggregate_df = aggregate_df.reindex(index_order)
    
    aggregate_df = aggregate_df.round(2).fillna('-').T

    return fig, aggregate_df