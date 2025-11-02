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
# 다른 모듈에서 생성된 데이터프레임을 임포트
from services.tables.common import START_DATE
from services.tables.HR_Core.basic_info_table import emp_df
from services.tables.HR_Core.salary_contract_info_table import salary_contract_info_df
from services.tables.Time_Attendance.daily_working_info_table import daily_work_info_df
from services.tables.Performance.evaluation_modified_score_info_table import evaluation_modified_score_df
from services.tables.Payroll.payroll_item_table import payroll_item_df

random.seed(42)
np.random.seed(42)
today = datetime.datetime.now().date()
today_ts = pd.to_datetime(today)

# --- 2. 헬퍼 데이터 준비 ---
salary_contract_info_df_sorted = salary_contract_info_df.sort_values(by=['SAL_START_DATE', 'EMP_ID'])
item_id_base = payroll_item_df[payroll_item_df['PAYROLL_ITEM_NAME'] == '기본급']['PAYROLL_ITEM_ID'].iloc[0]
item_id_bonus = payroll_item_df[payroll_item_df['PAYROLL_ITEM_NAME'] == '고정상여']['PAYROLL_ITEM_ID'].iloc[0]
item_id_meal = payroll_item_df[payroll_item_df['PAYROLL_ITEM_NAME'] == '식대']['PAYROLL_ITEM_ID'].iloc[0]
item_id_overtime = payroll_item_df[payroll_item_df['PAYROLL_ITEM_NAME'] == '시간외근로수당']['PAYROLL_ITEM_ID'].iloc[0]
item_id_incentive = payroll_item_df[payroll_item_df['PAYROLL_ITEM_NAME'] == '인센티브']['PAYROLL_ITEM_ID'].iloc[0]
item_id_ps = payroll_item_df[payroll_item_df['PAYROLL_ITEM_NAME'] == '기타성과급']['PAYROLL_ITEM_ID'].iloc[0]
item_cat_map = payroll_item_df.set_index('PAYROLL_ITEM_ID')['PAYROLL_ITEM_CATEGORY'].to_dict()

# --- 3. 스캐폴드 생성 및 연봉 정보 연결 ---
# 개발 모드: 2024-01-01부터, 프로덕션: 2020-01-01부터
min_hire_date = pd.to_datetime(max(emp_df['IN_DATE'].min(), pd.to_datetime(START_DATE)))
payroll_end_date = today.replace(day=1)
all_periods = pd.date_range(start=min_hire_date, end=payroll_end_date, freq='MS')
emp_ids = emp_df['EMP_ID'].unique()
scaffold_df = pd.DataFrame(list(product(emp_ids, all_periods)), columns=['EMP_ID', 'PAY_PERIOD_DT'])
scaffold_df = pd.merge(scaffold_df, emp_df[['EMP_ID', 'IN_DATE', 'OUT_DATE']], on='EMP_ID', how='left')
scaffold_df = scaffold_df[
    (scaffold_df['PAY_PERIOD_DT'] >= scaffold_df['IN_DATE'].dt.to_period('M').dt.to_timestamp()) &
    (pd.isna(scaffold_df['OUT_DATE']) | (scaffold_df['PAY_PERIOD_DT'] <= scaffold_df['OUT_DATE']))
].copy()
payroll_base_df = pd.merge_asof(
    scaffold_df.sort_values('PAY_PERIOD_DT'), salary_contract_info_df_sorted,
    left_on='PAY_PERIOD_DT', right_on='SAL_START_DATE', by='EMP_ID', direction='backward'
)
payroll_base_df = payroll_base_df.dropna(subset=['SAL_AMOUNT'])
payroll_base_df['SAL_AMOUNT'] = pd.to_numeric(payroll_base_df['SAL_AMOUNT'])

# --- 4. 기간별/항목별 급여 계산 ---
all_payroll_records = []

# 4-1. 일할계산 로직 사전 적용
payroll_base_df['PAY_PERIOD_M'] = payroll_base_df['PAY_PERIOD_DT'].dt.to_period('M')
payroll_base_df['IN_MONTH'] = payroll_base_df['IN_DATE'].dt.to_period('M')
payroll_base_df['OUT_MONTH'] = payroll_base_df['OUT_DATE'].dt.to_period('M')
payroll_base_df['DAYS_IN_MONTH'] = payroll_base_df['PAY_PERIOD_DT'].dt.days_in_month
work_days = payroll_base_df['DAYS_IN_MONTH'].copy()
in_month_mask = payroll_base_df['PAY_PERIOD_M'] == payroll_base_df['IN_MONTH']
work_days.loc[in_month_mask] = payroll_base_df['DAYS_IN_MONTH'] - payroll_base_df['IN_DATE'].dt.day + 1
out_month_mask = payroll_base_df['PAY_PERIOD_M'] == payroll_base_df['OUT_MONTH']
work_days.loc[out_month_mask] = payroll_base_df['OUT_DATE'].dt.day
payroll_base_df['PRORATION_RATE'] = work_days / payroll_base_df['DAYS_IN_MONTH']

# 4-2. 2022년 이전 (기본급, 고정상여)
pre_2022_df = payroll_base_df[payroll_base_df['PAY_PERIOD_DT'].dt.year < 2022].copy()
if not pre_2022_df.empty:
    pre_2022_df['BASE_PAYMENT_AMOUNT'] = np.ceil(pre_2022_df['SAL_AMOUNT'] / 18).astype(int)
    pre_2022_df['PRORATED_AMOUNT'] = np.ceil(pre_2022_df['BASE_PAYMENT_AMOUNT'] * pre_2022_df['PRORATION_RATE']).astype(int)
    base_pay_pre = pre_2022_df.copy(); base_pay_pre['PAYROLL_ITEM_ID'] = item_id_base; base_pay_pre['PAY_AMOUNT'] = base_pay_pre['PRORATED_AMOUNT']
    bonus_pre = pre_2022_df[pre_2022_df['PAY_PERIOD_DT'].dt.month.isin([2, 4, 6, 8, 10, 12])].copy()
    bonus_pre['PAYROLL_ITEM_ID'] = item_id_bonus; bonus_pre['PAY_AMOUNT'] = bonus_pre['PRORATED_AMOUNT']
    all_payroll_records.extend([base_pay_pre, bonus_pre])

# 4-3. 2022년 이후 (기본급)
post_2022_df = payroll_base_df[payroll_base_df['PAY_PERIOD_DT'].dt.year >= 2022].copy()
if not post_2022_df.empty:
    post_2022_df['MONTHLY_BASE_PAY'] = np.ceil(post_2022_df['SAL_AMOUNT'] / 12).astype(int)
    post_2022_df['PAY_AMOUNT'] = np.ceil(post_2022_df['MONTHLY_BASE_PAY'] * post_2022_df['PRORATION_RATE']).astype(int)
    post_2022_df['PAYROLL_ITEM_ID'] = item_id_base
    all_payroll_records.append(post_2022_df)

# 4-4. 식대
meal_allowance_df = payroll_base_df[payroll_base_df['PRORATION_RATE'] >= 0.8].copy()
meal_allowance_df['PAY_AMOUNT'] = np.where(meal_allowance_df['PAY_PERIOD_DT'].dt.year <= 2022, 100000, 200000)
meal_allowance_df['PAYROLL_ITEM_ID'] = item_id_meal
all_payroll_records.append(meal_allowance_df)

# 4-5. 시간외근로수당
ot_calc_df = daily_work_info_df.copy()
ot_calc_df['PAY_PERIOD_DT'] = ot_calc_df['DATE'].dt.to_period('M').dt.to_timestamp()
monthly_work_summary = ot_calc_df.groupby(['EMP_ID', 'PAY_PERIOD_DT']).agg(TOTAL_OVERTIME_HOURS=('OVERTIME_MINUTES', 'sum'),TOTAL_NIGHT_WORK_HOURS=('NIGHT_WORK_MINUTES', 'sum')).reset_index()
monthly_work_summary['TOTAL_OVERTIME_HOURS'] /= 60; monthly_work_summary['TOTAL_NIGHT_WORK_HOURS'] /= 60
ot_payroll_base = payroll_base_df[['EMP_ID', 'PAY_PERIOD_DT', 'SAL_AMOUNT']].copy()
ot_payroll_base = pd.merge(ot_payroll_base, monthly_work_summary, on=['EMP_ID', 'PAY_PERIOD_DT'], how='left').fillna(0)
ot_payroll_base['MONTHLY_BASE_FOR_OT'] = np.where(ot_payroll_base['PAY_PERIOD_DT'].dt.year < 2022, ot_payroll_base['SAL_AMOUNT'] / 18, ot_payroll_base['SAL_AMOUNT'] / 12)
ot_payroll_base['HOURLY_RATE'] = np.ceil(ot_payroll_base['MONTHLY_BASE_FOR_OT'] / 209)
ot_payroll_base['PAY_AMOUNT'] = np.ceil((ot_payroll_base['TOTAL_OVERTIME_HOURS'] * ot_payroll_base['HOURLY_RATE'] * 1.5) + (ot_payroll_base['TOTAL_NIGHT_WORK_HOURS'] * ot_payroll_base['HOURLY_RATE'] * 0.5)).astype(int)
ot_payroll_base['PAYROLL_ITEM_ID'] = item_id_overtime
overtime_allowance_df = ot_payroll_base[ot_payroll_base['PAY_AMOUNT'] > 0]
all_payroll_records.append(overtime_allowance_df)

# 4-6. 인센티브
incentive_records = []
eval_scores = evaluation_modified_score_df.copy()
for eval_time, group in eval_scores.groupby('EVAL_TIME'):
    group['SCORE_RANK_PCT'] = group['MODIFIED_SCORE'].rank(pct=True, ascending=False)
    conditions = [group['SCORE_RANK_PCT'] <= 0.10, group['SCORE_RANK_PCT'] <= 0.30]; choices = [2_000_000, 1_000_000]
    group['PAY_AMOUNT'] = np.select(conditions, choices, default=0)
    incentive_receivers = group[group['PAY_AMOUNT'] > 0].copy()
    year, period = eval_time.split('-'); pay_month = 6 if period == '상반기' else 12
    incentive_receivers['PAY_PERIOD_DT'] = pd.to_datetime(f'{year}-{pay_month}-01')
    incentive_receivers['PAYROLL_ITEM_ID'] = item_id_incentive
    incentive_records.append(incentive_receivers)
if incentive_records:
    incentive_df = pd.concat(incentive_records, ignore_index=True)
    all_payroll_records.append(incentive_df)

# 4-7. 기타성과급(Profit Sharing)
ps_records = []
analysis_years_ps = sorted(payroll_base_df['PAY_PERIOD_DT'].dt.year.unique())
for year in analysis_years_ps:
    min_rate = random.choice([0.05, 0.10, 0.15]); max_rate = min_rate + random.choice([0.10, 0.15])
    year_end_date = pd.to_datetime(date(year, 12, 31))
    eligible_emps_ps_df = emp_df[(emp_df['IN_DATE'] <= year_end_date) & (pd.isna(emp_df['OUT_DATE']) | (emp_df['OUT_DATE'] >= year_end_date))][['EMP_ID', 'IN_DATE']].copy()
    if eligible_emps_ps_df.empty: continue
    year_scores = evaluation_modified_score_df[(evaluation_modified_score_df['EVAL_YEAR'] == f"{year}년") & (evaluation_modified_score_df['EMP_ID'].isin(eligible_emps_ps_df['EMP_ID']))][['EMP_ID', 'YEAR_AVERAGE_SCORE']].copy()
    year_scores = year_scores.rename(columns={'YEAR_AVERAGE_SCORE': 'SCORE'})
    year_perf_data = pd.merge(eligible_emps_ps_df, year_scores, on='EMP_ID', how='left')
    no_score_mask = year_perf_data['SCORE'].isnull(); year_perf_data.loc[no_score_mask, 'SCORE'] = [random.uniform(60, 95) for _ in range(no_score_mask.sum())]
    december_period = pd.to_datetime(date(year, 12, 1))
    year_salaries = payroll_base_df[(payroll_base_df['PAY_PERIOD_DT'] == december_period)][['EMP_ID', 'SAL_AMOUNT']]
    year_perf_data = pd.merge(year_perf_data, year_salaries, on='EMP_ID')
    if year_perf_data.empty: continue
    days_in_year = 366 if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0) else 365
    year_perf_data['DAYS_WORKED'] = np.where(year_perf_data['IN_DATE'].dt.year == year, (pd.to_datetime(date(year, 12, 31)) - year_perf_data['IN_DATE']).dt.days + 1, days_in_year)
    year_perf_data['PRORATION_RATE'] = year_perf_data['DAYS_WORKED'] / days_in_year
    min_score, max_score = year_perf_data['SCORE'].min(), year_perf_data['SCORE'].max()
    score_range = max_score - min_score
    if score_range == 0: year_perf_data['BONUS_RATE'] = (min_rate + max_rate) / 2
    else: year_perf_data['BONUS_RATE'] = min_rate + ((year_perf_data['SCORE'] - min_score) / score_range) * (max_rate - min_rate)
    year_perf_data['PAY_AMOUNT'] = np.ceil((year_perf_data['SAL_AMOUNT'] * year_perf_data['PRORATION_RATE']) * year_perf_data['BONUS_RATE']).astype(int)
    year_perf_data['PAYROLL_ITEM_ID'] = item_id_ps; year_perf_data['PAY_PERIOD_DT'] = december_period
    ps_records.append(year_perf_data)
if ps_records:
    ps_df = pd.concat(ps_records, ignore_index=True)
    all_payroll_records.append(ps_df)

# --- 5. 원본/Google Sheets용 DataFrame 분리 ---
detailed_monthly_payroll_df = pd.DataFrame()
if all_payroll_records:
    detailed_monthly_payroll_df = pd.concat(all_payroll_records, ignore_index=True)
    detailed_monthly_payroll_df['PAY_PERIOD'] = detailed_monthly_payroll_df['PAY_PERIOD_DT'].dt.strftime('%Y-%m')
    detailed_monthly_payroll_df['PAY_DATE'] = (detailed_monthly_payroll_df['PAY_PERIOD_DT'] + pd.DateOffset(months=1)).dt.strftime('%Y-%m-10')
    detailed_monthly_payroll_df['PAYROLL_ITEM_CATEGORY'] = detailed_monthly_payroll_df['PAYROLL_ITEM_ID'].map(item_cat_map)
    final_cols = ['EMP_ID', 'PAY_PERIOD', 'PAY_DATE', 'PAYROLL_ITEM_ID', 'PAYROLL_ITEM_CATEGORY', 'PAY_AMOUNT']
    detailed_monthly_payroll_df = detailed_monthly_payroll_df[final_cols]
    detailed_monthly_payroll_df = detailed_monthly_payroll_df.sort_values(by=['EMP_ID', 'PAY_PERIOD', 'PAYROLL_ITEM_ID']).reset_index(drop=True)
    detailed_monthly_payroll_df['PAY_AMOUNT'] = pd.to_numeric(detailed_monthly_payroll_df['PAY_AMOUNT'])

detailed_monthly_payroll_df_for_gsheet = detailed_monthly_payroll_df.copy()
if not detailed_monthly_payroll_df_for_gsheet.empty:
    for col in detailed_monthly_payroll_df_for_gsheet.columns:
        detailed_monthly_payroll_df_for_gsheet[col] = detailed_monthly_payroll_df_for_gsheet[col].astype(str)
    detailed_monthly_payroll_df_for_gsheet = detailed_monthly_payroll_df_for_gsheet.replace({'None':'', 'NaT':'', 'nan':''})


# In[ ]:




