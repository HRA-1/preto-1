import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def create_figure_and_df(data_bundle, dimension_ui_name, drilldown_selection, dimension_config, order_map):
    """
    제안 17: 조직의 주간 리듬 분석 (요일별 업무 강도 및 휴가 패턴)
    dimension_config에 따라 동적으로 데이터를 필터링하여 이중 축 그래프를 생성합니다.
    """
    # 1. 데이터 및 설정 유효성 검사
    overtime_df = data_bundle.get("overtime_df")
    leave_df = data_bundle.get("leave_df")
    workable_days_df = data_bundle.get("workable_days_df")

    if any(df is None or df.empty for df in [overtime_df, leave_df, workable_days_df]):
        fig = go.Figure().update_layout(title_text="분석할 데이터가 없습니다.")
        return fig, pd.DataFrame()

    config = dimension_config.get(dimension_ui_name, {})
    if not config:
        fig = go.Figure().update_layout(title_text=f"'{dimension_ui_name}'에 대한 설정이 없습니다.")
        return fig, pd.DataFrame()

    # 2. 차원 설정에 따라 분석할 데이터(plot_df) 필터링
    # 이 그래프는 X축이 '요일'로 고정되므로, 선택된 차원은 데이터 필터링에만 사용됩니다.
    if drilldown_selection != '전체':
        filter_col = config.get('top', config.get('col'))
        
        ot_plot_df = overtime_df[overtime_df[filter_col] == drilldown_selection]
        leave_plot_df = leave_df[leave_df[filter_col] == drilldown_selection]
        workable_plot_df = workable_days_df[workable_days_df[filter_col] == drilldown_selection]
        
        title_text = f"'{drilldown_selection}'의 주간 리듬 분석"
    else:
        # '전체' 선택 시, 필터링 없이 전체 데이터 사용
        ot_plot_df = overtime_df
        leave_plot_df = leave_df
        workable_plot_df = workable_days_df
        title_text = '전사 주간 리듬 분석'

    # 3. 요일별 데이터 집계
    weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    
    # 3-1. 평균 초과근무 시간
    ot_summary = ot_plot_df.groupby('DAY_OF_WEEK')['OVERTIME_MINUTES'].mean().reindex(weekday_order, fill_value=0)
    
    # 3-2. 연차 사용률
    leave_days_sum = leave_plot_df.groupby('DAY_OF_WEEK')['LEAVE_LENGTH'].sum()
    workday_headcount = workable_plot_df.groupby('DAY_OF_WEEK').size()
    leave_summary = (leave_days_sum / workday_headcount * 100).reindex(weekday_order, fill_value=0)

    # 4. 이중 축 그래프 생성
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 막대그래프 (초과근무)
    fig.add_trace(go.Bar(
        x=ot_summary.index, 
        y=ot_summary.values, 
        name='평균 초과근무(분)'
    ), secondary_y=False)

    # 꺾은선그래프 (연차 사용률)
    fig.add_trace(go.Scatter(
        x=leave_summary.index, 
        y=leave_summary.values, 
        name='연차 사용률(%)',
        mode='lines+markers'
    ), secondary_y=True)

    # 5. 레이아웃 업데이트
    ot_max = ot_summary.max() if not ot_summary.empty else 0
    leave_rate_max = leave_summary.max() if not leave_summary.empty else 0
    fixed_y1_range = [0, ot_max * 1.2 if ot_max > 0 else 60]
    fixed_y2_range = [0, leave_rate_max * 1.2 if leave_rate_max > 0 else 10]

    fig.update_layout(
        template='plotly',
        title_text=title_text,
        font_size=14,
        height=700,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_xaxes(title_text="요일", categoryorder='array', categoryarray=weekday_order)
    fig.update_yaxes(title_text="평균 초과근무 시간 (분)", secondary_y=False, range=fixed_y1_range)
    fig.update_yaxes(title_text="요일별 연차 사용률 (%)", secondary_y=True, range=fixed_y2_range, ticksuffix="%")
    
    # 6. 요약 테이블(aggregate_df) 생성

    # 6-1. 현재 뷰에서 사용할 그룹핑 컬럼 및 데이터 결정
    if drilldown_selection != '전체':
        grouping_col = config.get('sub')
        source_ot_df, source_leave_df, source_workable_df = ot_plot_df, leave_plot_df, workable_plot_df
    else:
        grouping_col = config.get('top', config.get('col'))
        source_ot_df, source_leave_df, source_workable_df = overtime_df, leave_df, workable_days_df
    grouping_order = order_map.get(grouping_col, [])
    
    # 6-2. 각 지표에 대한 피벗 테이블과 '전체' 평균을 각각 생성
    # 초과근무
    ot_pivot = source_ot_df.pivot_table(index='DAY_OF_WEEK', columns=grouping_col, values='OVERTIME_MINUTES', aggfunc='mean', observed=False)
    ot_pivot['전체'] = ot_plot_df.groupby('DAY_OF_WEEK')['OVERTIME_MINUTES'].mean()
    ot_pivot['METRIC'] = '평균 초과근무시간(분)'

    # 연차사용률
    leave_pivot = (source_leave_df.pivot_table(index='DAY_OF_WEEK', columns=grouping_col, values='LEAVE_LENGTH', aggfunc='sum', observed=False) / 
                   source_workable_df.pivot_table(index='DAY_OF_WEEK', columns=grouping_col, aggfunc='size', observed=False)) * 100
    leave_pivot['전체'] = (leave_plot_df.groupby('DAY_OF_WEEK')['LEAVE_LENGTH'].sum() / 
                         workable_plot_df.groupby('DAY_OF_WEEK').size()) * 100
    leave_pivot['METRIC'] = '요일별 연차사용률(%)'
    
    # 6-3. 두 테이블을 합쳐 최종 MultiIndex 데이터프레임 생성
    aggregate_df = pd.concat([ot_pivot, leave_pivot])
    aggregate_df = aggregate_df.set_index('METRIC', append=True).reorder_levels(['METRIC', 'DAY_OF_WEEK'])
    
    # 6-4. 최종 정렬 및 포맷팅
    cols_ordered = ['전체'] + [col for col in grouping_order if col in aggregate_df.columns]
    metric_order = ['평균 초과근무시간(분)', '요일별 연차사용률(%)']
    aggregate_df = aggregate_df[cols_ordered].reindex(pd.MultiIndex.from_product([metric_order, weekday_order]))
    
    formatted_df = aggregate_df.copy()
    ot_slice = ('평균 초과근무시간(분)', slice(None))
    leave_slice = ('요일별 연차사용률(%)', slice(None))

    formatted_df.loc[ot_slice, :] = formatted_df.loc[ot_slice, :].applymap(lambda x: f"{x:.1f}" if pd.notna(x) else '-')
    formatted_df.loc[leave_slice, :] = formatted_df.loc[leave_slice, :].applymap(lambda x: f"{x:.2f}%" if pd.notna(x) else '-')
    aggregate_df = formatted_df.T
    
    return fig, aggregate_df