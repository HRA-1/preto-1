import pandas as pd
import plotly.graph_objects as go

def create_figure_and_df(data_bundle, dimension_ui_name, drilldown_selection, dimension_config, order_map):
    """
    제안 2: 차세대 리더 승진 경로 분석 (생키 다이어그램)
    사전 가공된 승진 경로 데이터(data_bundle)를 받아 인터랙티브 생키 다이어그램을 생성합니다.
    (dimension_ui_name 등은 app.py와의 호환성을 위해 받지만, 이 함수 내에서는 사용되지 않습니다.)
    """
    # 1. 데이터가 없는 경우 즉시 빈 그래프 반환
    if not data_bundle or "sankey_div_data" not in data_bundle:
        return go.Figure().update_layout(title_text="분석할 승진 경로 데이터가 없습니다.")

    # 2. 데이터 번들에서 부서별/직무별 데이터 추출
    sankey_div_bundle = data_bundle["sankey_div_data"]
    sankey_job_bundle = data_bundle["sankey_job_data"]
    
    labels_div = sankey_div_bundle["labels"]
    indices_div = sankey_div_bundle["indices"]
    sankey_div_df = sankey_div_bundle["data"]
    
    labels_job = sankey_job_bundle["labels"]
    indices_job = sankey_job_bundle["indices"]
    sankey_job_df = sankey_job_bundle["data"]
    
    # 3. Plotly 그래프 생성
    fig = go.Figure()

    # --- [수정된 부분 시작] ---
    # 색상 팔레트 정의 (필요에 따라 더 다양하게 정의할 수 있음)
    # Plotly 기본 색상 팔레트 사용 (예: 'Viridis', 'Plasma', 'Jet' 등)
    # 여기서는 각 노드의 색상을 다르게 지정하여 구분을 명확히 합니다.
    # 노드 색상을 자동으로 할당하는 대신, 특정 패턴을 따르도록 구현할 수 있습니다.
    # 예시: 'Staff'가 들어간 노드는 연한 파랑, 'Manager'는 중간 파랑, 'Director'는 진한 파랑
    # 또는 각 부서/직무별로 고유한 색상을 할당할 수도 있습니다.
    # 일단은 Plotly의 기본 색상 순서가 적용되도록 노드 색상을 None으로 두고,
    # 링크 색상만 좀 더 명확하게 설정하겠습니다.
    
    # 노드 색상을 동적으로 할당하는 헬퍼 함수 (예시)
    def get_node_colors(labels):
        colors = []
        # 미리 정의된 색상 팔레트 또는 로직을 사용할 수 있습니다.
        # 여기서는 단순히 라벨에 따라 다른 색을 할당하는 예시
        color_palette = [
            '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
            '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
        ]
        # 노드 레이블의 특정 키워드에 따라 색상 매핑
        node_color_map = {}
        for i, label in enumerate(labels):
            if 'Staff' in label:
                node_color_map[label] = 'lightblue'
            elif 'Manager' in label:
                node_color_map[label] = 'steelblue'
            elif 'Director' in label:
                node_color_map[label] = 'darkblue'
            else: # 그 외 노드는 팔레트 순서대로
                node_color_map[label] = color_palette[i % len(color_palette)]
        
        return [node_color_map[label] for label in labels]


    # 3-1. 부서별(Division Level) 생키 트레이스 추가 (기본으로 보임)
    fig.add_trace(go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=labels_div,
            color=get_node_colors(labels_div) # 노드 색상 지정
        ),
        link=dict(
            source=sankey_div_df['from_div'].map(indices_div),
            target=sankey_div_df['to_div'].map(indices_div),
            value=sankey_div_df['value'],
            color="rgba(0,0,255,0.4)" # 링크 색상 지정 (파란색 계열, 투명도 0.4)
        ),
        visible=True,
        name='Division View',
        domain=dict(x=[0, 1], y=[0, 1]) # 전체 영역 사용
    ))

    # 3-2. 직무별(Job Level) 생키 트레이스 추가 (기본으로 숨김)
    fig.add_trace(go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=labels_job,
            color=get_node_colors(labels_job) # 노드 색상 지정
        ),
        link=dict(
            source=sankey_job_df['from_job'].map(indices_job),
            target=sankey_job_df['to_job'].map(indices_job),
            value=sankey_job_df['value'],
            color="rgba(255,0,0,0.4)" # 링크 색상 지정 (빨간색 계열, 투명도 0.4)
        ),
        visible=False,
        name='Job View',
        domain=dict(x=[0, 1], y=[0, 1]) # 전체 영역 사용
    ))

    # 4. 드롭다운 메뉴 및 레이아웃 업데이트
    fig.update_layout(
        template='plotly', # Plotly의 다채로운 기본 테마 명시적 지정
        updatemenus=[dict(
            buttons=[
                dict(
                    label='부서별 경로',
                    method='update',
                    args=[{'visible': [True, False]},
                          {'title': '차세대 리더 승진 경로 분석 (부서별)'}]
                ),
                dict(
                    label='직무별 경로',
                    method='update',
                    args=[{'visible': [False, True]},
                          {'title': '차세대 리더 승진 경로 분석 (직무별)'}]
                )
            ],
            direction="down",
            pad={"r": 10, "t": 10},
            showactive=True,
            x=0.01,
            xanchor="left",
            y=1.1,
            yanchor="top"
        )],
        title_text="차세대 리더 승진 경로 분석 (부서별)", # 초기 제목 설정
        font_size=12,
        height=800,
        annotations=[dict(
            text="분석 기준:", 
            showarrow=False, 
            x=0, 
            y=1.08, 
            yref="paper", 
            align="left"
        )]
    )
    # --- [수정된 부분 끝] ---
    
    # 이 분석은 요약 테이블이 별도로 필요하지 않으므로, 빈 데이터프레임을 반환
    return fig, pd.DataFrame()