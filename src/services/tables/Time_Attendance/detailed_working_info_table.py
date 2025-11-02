#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd
import numpy as np
import datetime
from datetime import date, timedelta
import random
from itertools import product

# --- 1. 사전 준비 ---
# 다른 모듈에서 생성된 데이터프레임 및 헬퍼 데이터/함수를 임포트
from services.tables.common import START_DATE, END_DATE
from services.tables.HR_Core.basic_info_table import emp_df
from services.tables.HR_Core.department_table import department_df, parent_map_dept, dept_level_map, dept_name_map
from services.tables.HR_Core.department_info_table import department_info_df
from services.tables.Time_Attendance.working_system_table import work_sys_df
from services.tables.Time_Attendance.working_type_table import work_type_df
from services.tables.Time_Attendance.working_info_table import work_info_df
from services.helpers.utils import find_parents

random.seed(42)
np.random.seed(42)
today_date_obj = datetime.datetime.now().date()
start_date_range = START_DATE  # 개발 모드: 2024-01-01, 프로덕션: 2020-01-01
date_range_series = pd.to_datetime(pd.date_range(start=start_date_range, end=today_date_obj, freq='D'))
today_ts = pd.to_datetime(today_date_obj)

# --- 2. 헬퍼 데이터(퇴사자 그룹) 및 함수 정의 ---
leavers_df = emp_df[emp_df['CURRENT_EMP_YN'] == 'N'].copy()
leavers_shuffled = leavers_df.sample(frac=1, random_state=42)
burnout_leaver_ids = set(leavers_shuffled.iloc[:int(len(leavers_shuffled) * 0.3)]['EMP_ID'])
low_engagement_leaver_ids = set(leavers_shuffled.iloc[int(len(leavers_shuffled) * 0.3):int(len(leavers_shuffled) * 0.6)]['EMP_ID'])

shift_cycles = {'4조 2교대': ['주간', '야간', '비번', '휴무'], '4조 3교대': ['주간', '주간', '오후', '오후', '휴무', '야간', '야간', '비번', '휴무'], '3조 2교대': ['주간', '야간', '비번', '휴무'], '2조 2교대': ['주간', '야간', '비번', '휴무']}
def get_shift_type_vectorized(sys_name, days_since_hire, offset):
    cycle = shift_cycles.get(sys_name); return cycle[(days_since_hire + offset) % len(cycle)] if cycle else ''

# --- 3. 스캐폴드 생성 및 정보 통합 ---
emp_dates_df = emp_df[['EMP_ID', 'IN_DATE', 'OUT_DATE']].copy()
emp_ids = emp_dates_df['EMP_ID'].unique()
scaffold_index = pd.MultiIndex.from_product([emp_ids, date_range_series], names=['EMP_ID', 'DATE'])
df = pd.DataFrame(index=scaffold_index).reset_index()
df = pd.merge(df, emp_dates_df, on='EMP_ID', how='left')
df = df[(df['DATE'] >= df['IN_DATE']) & (pd.isna(df['OUT_DATE']) | (df['DATE'] <= df['OUT_DATE']))].copy()
df = pd.merge_asof(
    df.sort_values('DATE'),
    work_info_df.sort_values('WORK_ASSIGN_START_DATE'),
    left_on='DATE', right_on='WORK_ASSIGN_START_DATE', by='EMP_ID', direction='backward'
)
df = df.dropna(subset=['WORK_SYS_ID'])

# --- 4. 근무 유형 및 부서 정보 추가 ---
work_sys_name_map = work_sys_df.set_index('WORK_SYS_ID')['WORK_SYS_NAME'].to_dict()
df['WORK_SYS_NAME'] = df['WORK_SYS_ID'].map(work_sys_name_map)
is_shift_mask = df['WORK_SYS_NAME'] != '일반 근무'
df = pd.merge_asof(df.sort_values('DATE'), department_info_df.sort_values('DEP_APP_START_DATE'), left_on='DATE', right_on='DEP_APP_START_DATE', by='EMP_ID', direction='backward')
parent_info = df['DEP_ID'].apply(lambda x: find_parents(x, dept_level_map, parent_map_dept, dept_name_map))
df = pd.concat([df, parent_info], axis=1)
df['DAY_OF_WEEK'] = df['DATE'].dt.weekday; df['IS_WEEKEND'] = df['DAY_OF_WEEK'] >= 5
df['DAYS_SINCE_HIRE'] = (df['DATE'] - df['IN_DATE']).dt.days
shift_start_offsets_map = {emp_id: random.randint(0, 100) for emp_id in emp_ids}
df['SHIFT_OFFSET'] = df['EMP_ID'].map(shift_start_offsets_map)
df = df.dropna(subset=['WORK_SYS_NAME'])
df['WORK_TYPE_NAME'] = ''
if is_shift_mask.any():
    df.loc[is_shift_mask, 'WORK_TYPE_NAME'] = np.vectorize(get_shift_type_vectorized)(df.loc[is_shift_mask, 'WORK_SYS_NAME'], df.loc[is_shift_mask, 'DAYS_SINCE_HIRE'], df.loc[is_shift_mask, 'SHIFT_OFFSET'])
df.loc[~is_shift_mask, 'WORK_TYPE_NAME'] = '주간'

# --- 5. 휴가 생성 및 출퇴근 시간/비고 생성 ---
workable_day_mask = ~((df['WORK_SYS_NAME'] == '일반 근무') & df['IS_WEEKEND']) & ~df['WORK_TYPE_NAME'].isin(['비번', '휴무'])
workable_days_df = df[workable_day_mask].copy(); workable_days_df['YEAR'] = workable_days_df['DATE'].dt.year
sampled_dfs = [group.sample(n=min(len(group), random.randint(15, 25))) for name, group in workable_days_df.groupby(['EMP_ID', 'YEAR'])]
if sampled_dfs:
    vacation_df = pd.concat(sampled_dfs, ignore_index=True); vacation_df['IS_VACATION'] = True
    df = pd.merge(df, vacation_df[['EMP_ID', 'DATE', 'IS_VACATION']], on=['EMP_ID', 'DATE'], how='left')
df['IS_VACATION'] = df['IS_VACATION'].fillna(False).astype(bool)

df['WORK_ETC'] = np.where(df['IS_VACATION'], '휴가', np.where(is_shift_mask, df['WORK_SYS_NAME'] + '(' + df['WORK_TYPE_NAME'] + ')', np.where(df['IS_WEEKEND'], '주말 휴무', '일반 근무(평일)')))
df['DATE_START_TIME'] = '-'; df['DATE_END_TIME'] = '-'
work_day_mask = ~df['WORK_ETC'].isin(['휴가', '주말 휴무', '비번', '휴무'])
normal_work_mask = work_day_mask & ~is_shift_mask
shift_work_day_mask = work_day_mask & is_shift_mask

if normal_work_mask.sum() > 0:
    df.loc[normal_work_mask, 'START_HOURS'] = np.random.randint(8, 10, size=normal_work_mask.sum())
    df.loc[normal_work_mask, 'START_MINUTES'] = np.random.randint(0, 60, size=normal_work_mask.sum())
    df.loc[normal_work_mask, 'WORK_DURATION_MINUTES'] = 8 * 60 + np.random.randint(0, 181, size=normal_work_mask.sum())

    rd_mask = normal_work_mask & (df['OFFICE_NAME'] == 'R&D Office')
    if rd_mask.any(): df.loc[rd_mask, 'WORK_DURATION_MINUTES'] = 8 * 60 + np.random.randint(-60, 301, size=rd_mask.sum())
    strategy_mask = normal_work_mask & (df['OFFICE_NAME'] == 'Strategy Office')
    if strategy_mask.any(): df.loc[strategy_mask, 'WORK_DURATION_MINUTES'] = 8 * 60 + np.random.randint(0, 241, size=strategy_mask.sum())
    gs_mask = normal_work_mask & (df['OFFICE_NAME'] == 'Global Sales Office')
    if gs_mask.any(): df.loc[gs_mask, 'START_HOURS'] = np.random.randint(9, 11, size=gs_mask.sum())

    df['ONE_YEAR_BEFORE_OUT'] = df['OUT_DATE'] - pd.DateOffset(years=1)
    burnout_mask = normal_work_mask & (df['EMP_ID'].isin(burnout_leaver_ids)) & (df['DATE'] >= df['ONE_YEAR_BEFORE_OUT'])
    if burnout_mask.any(): df.loc[burnout_mask, 'WORK_DURATION_MINUTES'] = 8 * 60 + np.random.randint(120, 300, size=burnout_mask.sum())
    low_engagement_mask = normal_work_mask & (df['EMP_ID'].isin(low_engagement_leaver_ids)) & (df['DATE'] >= df['ONE_YEAR_BEFORE_OUT'])
    if low_engagement_mask.any(): df.loc[low_engagement_mask, 'WORK_DURATION_MINUTES'] = 8 * 60 + np.random.randint(0, 31, size=low_engagement_mask.sum())

    df.loc[normal_work_mask, 'DATE_START_TIME'] = [f"{int(h):02d}:{int(m):02d}" for h, m in zip(df.loc[normal_work_mask, 'START_HOURS'], df.loc[normal_work_mask, 'START_MINUTES'])]
    valid_starts_mask = normal_work_mask & pd.to_datetime(df['DATE_START_TIME'], format='%H:%M', errors='coerce').notna()
    if valid_starts_mask.any():
        start_dt = pd.to_datetime(df.loc[valid_starts_mask, 'DATE'].astype(str) + ' ' + df.loc[valid_starts_mask, 'DATE_START_TIME'])
        timedeltas = pd.to_timedelta(df.loc[valid_starts_mask, 'WORK_DURATION_MINUTES'], unit='m'); timedeltas.index = start_dt.index
        end_datetimes = start_dt + timedeltas
        df.loc[valid_starts_mask, 'DATE_END_TIME'] = end_datetimes.dt.strftime('%H:%M')

if shift_work_day_mask.any():
    shift_df = df[shift_work_day_mask].copy()
    shift_df = pd.merge(shift_df, work_type_df, on=['WORK_SYS_ID', 'WORK_TYPE_NAME'], how='left')
    shift_df['SCHED_START_DT'] = pd.to_datetime(shift_df['DATE'].dt.strftime('%Y-%m-%d') + ' ' + shift_df['WORK_START_TIME'], errors='coerce')
    shift_df['SCHED_END_DT'] = pd.to_datetime(shift_df['DATE'].dt.strftime('%Y-%m-%d') + ' ' + shift_df['WORK_END_TIME'], errors='coerce')
    overnight_mask = shift_df['SCHED_END_DT'] < shift_df['SCHED_START_DT']
    shift_df.loc[overnight_mask, 'SCHED_END_DT'] += pd.Timedelta(days=1)
    shift_df['SHIFT_OVERTIME'] = np.where(np.random.rand(len(shift_df)) < 0.2, np.random.randint(60, 121, size=len(shift_df)), 0)
    prod_shift_mask = shift_df['OFFICE_NAME'] == 'Production Office'
    if prod_shift_mask.any():
        shift_df.loc[prod_shift_mask, 'SHIFT_OVERTIME'] = np.random.randint(60, 181, size=prod_shift_mask.sum())
    shift_df['FINAL_END_DT'] = shift_df['SCHED_END_DT'] + pd.to_timedelta(shift_df['SHIFT_OVERTIME'], unit='m')
    df.loc[shift_work_day_mask, 'DATE_START_TIME'] = shift_df['WORK_START_TIME']
    df.loc[shift_work_day_mask, 'DATE_END_TIME'] = shift_df['FINAL_END_DT'].dt.strftime('%H:%M')

# --- 6. 최종 DataFrame 정리 ---
final_columns = ['EMP_ID', 'DATE', 'DATE_START_TIME', 'DATE_END_TIME', 'WORK_ETC']
detailed_work_info_df = df[final_columns].copy()
detailed_work_info_df_for_gsheet = detailed_work_info_df.copy()
start_date_for_sheet = pd.to_datetime('2023-01-01')
detailed_work_info_df_for_gsheet = detailed_work_info_df_for_gsheet[detailed_work_info_df_for_gsheet['DATE'] >= start_date_for_sheet].copy()
detailed_work_info_df_for_gsheet['DATE'] = detailed_work_info_df_for_gsheet['DATE'].dt.strftime('%Y-%m-%d')
for col in detailed_work_info_df_for_gsheet.columns:
    detailed_work_info_df_for_gsheet[col] = detailed_work_info_df_for_gsheet[col].astype(str)
detailed_work_info_df_for_gsheet = detailed_work_info_df_for_gsheet.replace({'None':'', 'NaT':'', 'nan':''})


# In[ ]:




