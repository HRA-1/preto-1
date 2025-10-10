import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pandas.api.types import is_categorical_dtype

def create_figure_and_df(data_bundle, dimension_ui_name, period_agg_name, subgroup_name, dimension_config):
    """
    제안 0: 기본 인원 변동 현황 그래프 및 요약 테이블을 생성합니다.
    dimension_config에 따라 동적으로 X축과 필터를 처리합니다.
    """
    # 1. 데이터 선택
    # config에서 필요한 컬럼명과 순서 정보 등을 가져옴
    config = dimension_config.get(dimension_ui_name, {})
    dimension_col = config.get('top', config.get('col'))
    
    dimension_data = data_bundle.get(dimension_ui_name, data_bundle.get('전체', {}))
    summary_df_for_agg = dimension_data.get(period_agg_name, pd.DataFrame())
    overall_summary_df_for_agg = data_bundle.get('전체', {}).get(period_agg_name, pd.DataFrame())

    if summary_df_for_agg.empty or overall_summary_df_for_agg.empty:
        fig = go.Figure().update_layout(title_text="표시할 데이터가 없습니다.")
        return fig, pd.DataFrame()

    # 2. 기간(PERIOD) 컬럼 생성
    period_source_col = 'QUARTER' if period_agg_name == 'quarterly' else 'YEAR' if period_agg_name == 'yearly' else 'PERIOD_DT'
    for df in [summary_df_for_agg, overall_summary_df_for_agg]:
        if period_agg_name == 'quarterly':
            df['PERIOD'] = df[period_source_col].apply(lambda q: f"{q.year}년 {q.quarter}분기")
        elif period_agg_name == 'yearly':
            df['PERIOD'] = df[period_source_col].apply(lambda y: f"{y}년")
        else: # monthly
            df['PERIOD'] = df[period_source_col].dt.strftime('%Y년 %m월')
    
    # 3. 그래프용 데이터(plot_df) 최종 선택
    if subgroup_name == '전체' or not dimension_col:
        plot_df = overall_summary_df_for_agg.tail(12)
        title = f"{period_agg_name.replace('ly','별')} 인원 변동 현황"
    else:
        plot_df = summary_df_for_agg[summary_df_for_agg[dimension_col] == subgroup_name].tail(12)
        title = f"[{subgroup_name}] {period_agg_name.replace('ly','별')} 인원 변동 현황"

    # 4. 그래프 생성
    if plot_df.empty:
        fig = go.Figure().update_layout(title_text=f"'{subgroup_name}'에 대한 데이터가 없습니다.")
    else:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=plot_df['PERIOD'], y=plot_df['NEW_HIRES'], name='입사자', marker_color='blue'), secondary_y=False)
        fig.add_trace(go.Bar(x=plot_df['PERIOD'], y=plot_df['LEAVERS'], name='퇴사자', marker_color='red'), secondary_y=False)
        fig.add_trace(go.Scatter(x=plot_df['PERIOD'], y=plot_df['HEADCOUNT'], name='총원', mode='lines+markers+text', text=plot_df['HEADCOUNT'], textposition='top center', line=dict(color='black')), secondary_y=True)
        
        max_val = max(plot_df['NEW_HIRES'].max(), plot_df['LEAVERS'].max())
        y1_range = [0, max_val * 1.5 if max_val > 0 else 10]
        
        fig.update_layout(
            template='plotly',
            title_text=title,
            xaxis_title='기간',
            font_size=14,
            height=700,
            barmode='group',
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        fig.update_yaxes(title_text="입사/퇴사자 수", secondary_y=False, range=y1_range)
        fig.update_yaxes(title_text="총원", secondary_y=True, rangemode='tozero')
    
    # 5. 요약 테이블(aggregate_df) 생성
    aggregate_df = pd.DataFrame()
    if not summary_df_for_agg.empty and not overall_summary_df_for_agg.empty and dimension_col:
        agg_by_dim = summary_df_for_agg.pivot_table(index='PERIOD', columns=dimension_col, values='HEADCOUNT', aggfunc='last')
        agg_overall = overall_summary_df_for_agg.pivot_table(index='PERIOD', values='HEADCOUNT', aggfunc='last').rename(columns={'HEADCOUNT': '전체'})
        
        aggregate_df = pd.concat([agg_overall, agg_by_dim], axis=1).fillna(0).astype(int)
        
        # 컬럼 순서 재정렬
        cols_ordered = ['전체']
        # config에 정의된 순서(order)가 있으면 사용
        if 'order' in config and config['order'] is not None:
             ordered_categories = config['order']
             cols_ordered += [col for col in ordered_categories if col in aggregate_df.columns]
        else: # 없으면 정렬된 unique 값 사용
             ordered_categories = sorted(summary_df_for_agg[dimension_col].unique())
             cols_ordered += [col for col in ordered_categories if col in aggregate_df.columns]
        
        final_cols = [col for col in cols_ordered if col in aggregate_df.columns]
        aggregate_df = aggregate_df[final_cols]
        
        aggregate_df = aggregate_df.tail(12)

    return fig, aggregate_df