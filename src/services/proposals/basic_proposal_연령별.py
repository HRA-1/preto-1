#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
import datetime

# --- 1. 데이터 임포트 ---
from services.tables.HR_Core.basic_info_table import emp_df
from services.helpers.utils import calculate_age


def create_figure():
    """
    제안 0-4: 연령별 분기 인원 변동 현황 그래프를 생성합니다.
    """
    # --- 2. 데이터 준비 및 가공 ---
    emp_dates_df = emp_df[["EMP_ID", "PERSONAL_ID", "IN_DATE", "OUT_DATE"]].copy()
    emp_dates_df["IN_DATE"] = pd.to_datetime(emp_dates_df["IN_DATE"])
    emp_dates_df["OUT_DATE"] = pd.to_datetime(emp_dates_df["OUT_DATE"])

    age_bins = [-1, 19, 29, 39, 49, 150]
    age_labels = ["20세 미만", "20-29세", "30-39세", "40-49세", "50세 이상"]

    start_month = emp_dates_df["IN_DATE"].min().to_period("M").to_timestamp()
    end_month = pd.to_datetime(datetime.datetime.now()).to_period("M").to_timestamp()
    monthly_periods = pd.date_range(start=start_month, end=end_month, freq="MS")

    monthly_summary_records = []
    for period_start in monthly_periods:
        period_end = period_start + pd.offsets.MonthEnd(0)

        hires_df = emp_dates_df[
            emp_dates_df["IN_DATE"].between(period_start, period_end)
        ].copy()
        leavers_df = emp_dates_df[
            emp_dates_df["OUT_DATE"].between(period_start, period_end)
        ].copy()
        active_df = emp_dates_df[
            (emp_dates_df["IN_DATE"] <= period_end)
            & (
                (emp_dates_df["OUT_DATE"].isnull())
                | (emp_dates_df["OUT_DATE"] > period_end)
            )
        ].copy()

        if not hires_df.empty:
            hires_df["AGE_AT_EVENT"] = hires_df.apply(
                lambda row: calculate_age(row["PERSONAL_ID"], row["IN_DATE"]), axis=1
            )
            hires_df["AGE_BIN"] = pd.cut(
                hires_df["AGE_AT_EVENT"], bins=age_bins, labels=age_labels
            )
            hires_by_age = hires_df.groupby("AGE_BIN", observed=False).size()
        else:
            hires_by_age = pd.Series(dtype=int)

        if not leavers_df.empty:
            leavers_df["AGE_AT_EVENT"] = leavers_df.apply(
                lambda row: calculate_age(row["PERSONAL_ID"], row["OUT_DATE"]), axis=1
            )
            leavers_df["AGE_BIN"] = pd.cut(
                leavers_df["AGE_AT_EVENT"], bins=age_bins, labels=age_labels
            )
            leavers_by_age = leavers_df.groupby("AGE_BIN", observed=False).size()
        else:
            leavers_by_age = pd.Series(dtype=int)

        if not active_df.empty:
            active_df["AGE_AT_EVENT"] = active_df["PERSONAL_ID"].apply(
                lambda pid: calculate_age(pid, base_date=period_end)
            )
            active_df["AGE_BIN"] = pd.cut(
                active_df["AGE_AT_EVENT"], bins=age_bins, labels=age_labels
            )
            headcount_by_age = active_df.groupby("AGE_BIN", observed=False).size()
        else:
            headcount_by_age = pd.Series(dtype=int)

        all_ages_in_period = (
            set(hires_by_age.index)
            | set(leavers_by_age.index)
            | set(headcount_by_age.index)
        )

        for age_bin in all_ages_in_period:
            if pd.notna(age_bin):
                monthly_summary_records.append(
                    {
                        "PERIOD_DT": period_start,
                        "AGE_BIN": age_bin,
                        "NEW_HIRES": hires_by_age.get(age_bin, 0),
                        "LEAVERS": leavers_by_age.get(age_bin, 0),
                        "HEADCOUNT": headcount_by_age.get(age_bin, 0),
                    }
                )

    monthly_age_summary_df = pd.DataFrame(monthly_summary_records)

    monthly_age_summary_df["QUARTER"] = monthly_age_summary_df[
        "PERIOD_DT"
    ].dt.to_period("Q")
    quarterly_age_summary_df = (
        monthly_age_summary_df.groupby(["QUARTER", "AGE_BIN"], observed=False)
        .agg(
            NEW_HIRES=("NEW_HIRES", "sum"),
            LEAVERS=("LEAVERS", "sum"),
            HEADCOUNT=("HEADCOUNT", "last"),
        )
        .reset_index()
    )

    quarterly_overall_summary_df = (
        quarterly_age_summary_df.groupby("QUARTER")
        .agg(
            NEW_HIRES=("NEW_HIRES", "sum"),
            LEAVERS=("LEAVERS", "sum"),
            HEADCOUNT=("HEADCOUNT", "sum"),
        )
        .reset_index()
    )

    for df in [quarterly_age_summary_df, quarterly_overall_summary_df]:
        df["PERIOD"] = df["QUARTER"].apply(lambda q: f"{q.year}년 {q.quarter}분기")

    # --- 3. Plotly 인터랙티브 그래프 생성 ---
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    age_bin_list = ["전체"] + age_labels

    trace_map = {"전체": quarterly_overall_summary_df}
    for age_bin in age_labels:
        trace_map[age_bin] = quarterly_age_summary_df[
            quarterly_age_summary_df["AGE_BIN"] == age_bin
        ]

    for name, df in trace_map.items():
        is_visible = name == "전체"
        df_plot = df.tail(12).copy()
        fig.add_trace(
            go.Bar(
                x=df_plot["PERIOD"],
                y=df_plot["NEW_HIRES"],
                name="입사자",
                marker_color="blue",
                visible=is_visible,
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Bar(
                x=df_plot["PERIOD"],
                y=df_plot["LEAVERS"],
                name="퇴사자",
                marker_color="red",
                visible=is_visible,
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=df_plot["PERIOD"],
                y=df_plot["HEADCOUNT"],
                name="총원",
                mode="lines+markers+text",
                text=df_plot["HEADCOUNT"],
                textposition="top center",
                line=dict(color="black"),
                visible=is_visible,
            ),
            secondary_y=True,
        )

    # --- 4. 드롭다운 메뉴 및 레이아웃 업데이트 ---
    buttons = []
    num_traces_per_group = 3
    for i, name in enumerate(age_bin_list):
        visibility_mask = [False] * (len(age_bin_list) * num_traces_per_group)
        for j in range(num_traces_per_group):
            visibility_mask[i * num_traces_per_group + j] = True
        df_for_range = trace_map[name].tail(12)
        max_hires_leavers = (
            max(df_for_range["NEW_HIRES"].max(), df_for_range["LEAVERS"].max())
            if not df_for_range.empty
            else 0
        )
        y1_range = [0, max_hires_leavers * 2.2]
        buttons.append(
            dict(
                label=name,
                method="update",
                args=[{"visible": visibility_mask}, {"yaxis.range": y1_range}],
            )
        )

    initial_df = trace_map["전체"].tail(12)
    initial_max = (
        max(initial_df["NEW_HIRES"].max(), initial_df["LEAVERS"].max())
        if not initial_df.empty
        else 0
    )
    initial_y1_range = [0, initial_max * 2.2]

    fig.update_layout(
        updatemenus=[
            dict(
                active=0,
                buttons=buttons,
                direction="down",
                pad={"r": 10, "t": 10},
                showactive=True,
                x=0.01,
                xanchor="left",
                y=1.1,
                yanchor="top",
            )
        ],
        title_text="연령별 분기 인원 변동 현황",
        xaxis_title="분기",
        font_size=14,
        height=700,
        barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        annotations=[
            dict(
                text="연령대 선택:",
                showarrow=False,
                x=0,
                y=1.08,
                yref="paper",
                align="left",
            )
        ],
    )
    fig.update_yaxes(
        title_text="입사/퇴사자 수", secondary_y=False, range=initial_y1_range
    )
    fig.update_yaxes(title_text="총원", secondary_y=True, rangemode="tozero")

    return fig


# 이 파일을 직접 실행할 경우 그래프를 생성하여 보여줍니다.
pio.renderers.default = "vscode"
fig = create_figure()
fig.show()


# In[ ]:
