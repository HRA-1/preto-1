import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from pandas.api.types import is_categorical_dtype

def create_figure_and_df(data_bundle, dimension_ui_name, drilldown_selection, dimension_config, order_map):
    """
    제안 20: 조직별 휴가 사용 패턴 분석 (Team별 휴가 유형 진단)
    '연도별' 필터, '동적 축 범위', 'MultiIndex 정렬'을 모두 적용합니다.
    """
    # data_bundle에서 analysis_df 추출
    analysis_df = data_bundle.get("analysis_df", pd.DataFrame())
    
    # 1. 데이터 유효성 검사
    if analysis_df.empty or 'IS_BRIDGE' not in analysis_df.columns:
        fig = go.Figure().update_layout(title_text="분석할 데이터가 없습니다.")
        return fig, pd.DataFrame()

    config = dimension_config.get(dimension_ui_name, {})
    if not config:
        fig = go.Figure().update_layout(title_text=f"'{dimension_ui_name}'에 대한 설정이 없습니다.")
        return fig, pd.DataFrame()
    
    # 2. 분석 차원 및 연도 정의 (2020년 이후 데이터만 사용)
    analysis_df = analysis_df[analysis_df['YEAR'] >= 2020].copy()
    
    grouping_col = config.get('top', config.get('col'))
    group_order = order_map.get(grouping_col, sorted(analysis_df[grouping_col].unique()))
    
    available_years = sorted(analysis_df['YEAR'].unique(), reverse=True)
    if not available_years:
        fig = go.Figure().update_layout(title_text="분석할 연도 데이터가 없습니다.")
        return fig, pd.DataFrame()

    colors = px.colors.qualitative.Plotly
    color_map = {str(group): colors[i % len(colors)] for i, group in enumerate(group_order)}
    fig = go.Figure()

    # 3. 연도별, 그룹별로 팀 휴가 패턴 집계 및 트레이스 추가
    trace_count_per_year = len(group_order)
    x_ranges, y_ranges = [], []
    all_team_summaries = [] # 테이블 생성을 위해 모든 연도의 요약 데이터 저장

    for year in available_years:
        df_year = analysis_df[analysis_df['YEAR'] == year]
        is_visible = (year == available_years[0])
        
        team_summary = df_year.groupby([grouping_col, 'TEAM_NAME'], observed=True).agg(
            BRIDGE_LEAVE_DAYS=('IS_BRIDGE', 'sum'),
            LONG_LEAVE_DAYS=('IS_LONG_LEAVE', 'sum'),
            TOTAL_LEAVE_DAYS=('EMP_ID', 'count'),
            HEADCOUNT=('EMP_ID', 'nunique')
        )
        team_summary['BRIDGE_LEAVE_RATE'] = (team_summary['BRIDGE_LEAVE_DAYS'] / team_summary['TOTAL_LEAVE_DAYS'] * 100).fillna(0)
        team_summary['LONG_LEAVE_RATE'] = (team_summary['LONG_LEAVE_DAYS'] / team_summary['TOTAL_LEAVE_DAYS'] * 100).fillna(0)
        team_summary = team_summary.reset_index()
        team_summary['YEAR'] = year
        
        all_team_summaries.append(team_summary)

        if not team_summary.empty:
            x_ranges.extend(team_summary['BRIDGE_LEAVE_RATE'].dropna().tolist())
            y_ranges.extend(team_summary['LONG_LEAVE_RATE'].dropna().tolist())

        # ----- [수정된 부분 1: 빈 트레이스 추가] -----
        # `visible` 마스크가 꼬이지 않도록, 데이터가 없어도 빈 트레이스를 추가
        for i, group_name in enumerate(group_order):
            df_group = team_summary[team_summary[grouping_col] == group_name]
            
            if not df_group.empty:
                hovertemplate_str = (
                    "<b>팀: %{text}</b><br>" +
                    f"{dimension_ui_name}: %{{customdata[0]}}<br>" +
                    "징검다리 휴가율: %{x:.1f}%<br>" +
                    "장기 휴가율: %{y:.1f}%<br>" +
                    "팀 인원수: %{customdata[1]}" +
                    "<extra></extra>"
                )
                
                fig.add_trace(go.Scatter(
                    x=df_group['BRIDGE_LEAVE_RATE'],
                    y=df_group['LONG_LEAVE_RATE'],
                    mode='markers',
                    marker=dict(color=color_map.get(str(group_name)), size=df_group['HEADCOUNT'], sizemin=4, sizeref=max(1, team_summary['HEADCOUNT'].max() / 50.)),
                    name=str(group_name),
                    legendgroup=str(group_name),
                    showlegend=bool(year == available_years[0]), # bool()로 타입 변환
                    visible=is_visible,
                    text=df_group['TEAM_NAME'],
                    hovertemplate=hovertemplate_str,
                    customdata=np.stack((df_group[grouping_col], df_group['HEADCOUNT']), axis=-1)
                ))
            else:
                # 데이터가 없는 그룹도 인덱스 순서를 맞추기 위해 빈 트레이스 추가
                fig.add_trace(go.Scatter(x=None, y=None, mode='markers', name=str(group_name), legendgroup=str(group_name), showlegend=bool(year == available_years[0]), visible=is_visible))
        # ----- [수정된 부분 1 끝] -----

    # 4. 사분면 기준선 및 동적 레이아웃 업데이트
    df_initial_summary = analysis_df[analysis_df['YEAR'] == available_years[0]].groupby('TEAM_NAME', observed=True).agg(
        BRIDGE_LEAVE_DAYS=('IS_BRIDGE', 'sum'), LONG_LEAVE_DAYS=('IS_LONG_LEAVE', 'sum'),
        TOTAL_LEAVE_DAYS=('EMP_ID', 'count')
    )
    x_median_initial = (df_initial_summary['BRIDGE_LEAVE_DAYS'] / df_initial_summary['TOTAL_LEAVE_DAYS'] * 100).median()
    y_median_initial = (df_initial_summary['LONG_LEAVE_DAYS'] / df_initial_summary['TOTAL_LEAVE_DAYS'] * 100).median()
    
    fig.add_vline(x=x_median_initial, line_width=1, line_dash="dash", line_color="grey")
    fig.add_hline(y=y_median_initial, line_width=1, line_dash="dash", line_color="grey")
    
    x_min, x_max = (min(x_ranges), max(x_ranges)) if x_ranges else (0, 100)
    y_min, y_max = (min(y_ranges), max(y_ranges)) if y_ranges else (0, 100)
    x_pad = (x_max - x_min) * 0.1; y_pad = (y_max - y_min) * 0.1
    fixed_x_range = [max(0, x_min - x_pad), min(100, x_max + x_pad)]
    fixed_y_range = [max(0, y_min - y_pad), min(100, y_max + y_pad)]
    
    # 5. 드롭다운 버튼 생성
    buttons = []
    for i, year in enumerate(available_years):
        visibility_mask = [False] * len(fig.data)
        start_idx = i * trace_count_per_year
        end_idx = start_idx + trace_count_per_year
        visibility_mask[start_idx:end_idx] = [True] * trace_count_per_year
        
        df_year_summary = analysis_df[analysis_df['YEAR'] == year].groupby('TEAM_NAME', observed=True).agg(
            BRIDGE_LEAVE_DAYS=('IS_BRIDGE', 'sum'), LONG_LEAVE_DAYS=('IS_LONG_LEAVE', 'sum'),
            TOTAL_LEAVE_DAYS=('EMP_ID', 'count')
        )
        x_median_year = (df_year_summary['BRIDGE_LEAVE_DAYS'] / df_year_summary['TOTAL_LEAVE_DAYS'] * 100).median()
        y_median_year = (df_year_summary['LONG_LEAVE_DAYS'] / df_year_summary['TOTAL_LEAVE_DAYS'] * 100).median()
        
        buttons.append(dict(label=str(year), method='update', args=[
            {'visible': visibility_mask, 'showlegend': [bool((idx // trace_count_per_year) == i) for idx in range(len(fig.data))]},
            {'shapes': [
                dict(type="line", x0=x_median_year, x1=x_median_year, y0=fixed_y_range[0], y1=fixed_y_range[1], line=dict(width=1, dash="dash", color="grey")),
                dict(type="line", y0=y_median_year, y1=y_median_year, x0=fixed_x_range[0], x1=fixed_x_range[1], line=dict(width=1, dash="dash", color="grey"))
            ]}
        ]))

    fig.update_layout(
        template='plotly',
        updatemenus=[dict(active=0, buttons=buttons, direction="down", pad={"r": 10, "t": 10}, showactive=True, x=0.01, xanchor="left", y=1.1, yanchor="top")],
        title_text=f"팀별 연차 사용 패턴 ({dimension_ui_name} 기준)",
        xaxis_title='징검다리 휴가 사용률 (%)', yaxis_title='장기 휴가 사용률 (%)',
        font_size=14, height=700,
        xaxis_range=fixed_x_range, yaxis_range=fixed_y_range,
        legend_title_text=dimension_ui_name,
        annotations=[dict(text="연도 선택:", showarrow=False, x=0, y=1.08, yref="paper", align="left")]
    )
    
    # 6. 요약 테이블(aggregate_df) 생성
    
    # 6-1. 모든 연도의 요약 데이터를 하나로 합침
    if not all_team_summaries:
        return fig, pd.DataFrame()
        
    full_team_summary = pd.concat(all_team_summaries, ignore_index=True)
    
    # 6-2. pivot_table을 사용하여 최종 형태로 한 번에 변환
    aggregate_df = full_team_summary.pivot_table(
        index='TEAM_NAME', 
        columns='YEAR',
        values=['BRIDGE_LEAVE_RATE', 'LONG_LEAVE_RATE', 'HEADCOUNT']
    )
    
    # 6-3. 컬럼 레벨 순서 변경: (Metric, Year) -> (Year, Metric)
    if not aggregate_df.empty:
        aggregate_df = aggregate_df.swaplevel(0, 1, axis=1).sort_index(axis=1)
    
        # 6-4. 컬럼 순서 지정
        metric_order = ['BRIDGE_LEAVE_RATE', 'LONG_LEAVE_RATE', 'HEADCOUNT']
        year_order = sorted(available_years)
        
        aggregate_df.columns = aggregate_df.columns.set_levels(
            aggregate_df.columns.levels[1].str.replace('HEADCOUNT', '팀 인원수'), level=1
        )
        metric_order[2] = '팀 인원수' # 이름 변경에 맞춰 metric_order도 수정
        
        aggregate_df = aggregate_df.reindex(columns=pd.MultiIndex.from_product([year_order, metric_order]))
    
    aggregate_df = aggregate_df.sort_index()
    
    return fig, aggregate_df.round(1).fillna('-')