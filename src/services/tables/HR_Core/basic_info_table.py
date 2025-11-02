#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd
import numpy as np
import datetime
from datetime import date, timedelta
from faker import Faker
import random
from services.tables.common import TOTAL_EMPLOYEES

# ==============================================================================
# --- 10. BASIC INFO TABLE (기본정보) ---
# ==============================================================================

# --- 1. 사전 준비 ---
fake_kr = Faker("ko_KR")
fake_en = Faker("en_US")
Faker.seed(42)
random.seed(42)
np.random.seed(42)

num_employees = TOTAL_EMPLOYEES  # 개발 모드: 50명, 프로덕션: 1000명
today = datetime.datetime.now().date()
today_ts = pd.to_datetime(today)

# --- 2. 1단계: 모든 직원을 '재직' 상태로 초기 데이터 생성 ---
initial_employees = []
for i in range(1, num_employees + 1):
    emp_id = f"E{i:05d}"
    name = fake_kr.name()
    eng_name = fake_en.name()
    nickname = fake_en.first_name()
    birth_date = fake_kr.date_of_birth(minimum_age=25, maximum_age=45)
    birth_str = birth_date.strftime("%y%m%d")
    gender_code = random.choice(["3", "4"]) if birth_date.year >= 2000 else random.choice(["1", "2"])
    gender = "M" if gender_code in ["1", "3"] else "F"
    unique_digits = f"{random.randint(0, 999999):06d}"
    personal_id = f"{birth_str}-{gender_code}{unique_digits}"
    email = fake_en.email()
    phone_num = fake_kr.phone_number()
    in_date = fake_kr.date_between(start_date="-15y", end_date="-30d")
    group_in_date = in_date
    if random.random() > 0.925:
        group_in_date = in_date - timedelta(days=random.randint(1, 1000))
    nationality = random.choices(["Korea", "USA", "China", "Vietnam", "Philippines", "India"],
                                 weights=[0.7, 0.05, 0.05, 0.05, 0.05, 0.1])[0]
    address = fake_kr.address()
    initial_employees.append({
        "EMP_ID": emp_id, "NAME": name, "ENG_NAME": eng_name, "NICKNAME": nickname,
        "PERSONAL_ID": personal_id, "GENDER": gender, "EMAIL": email, "PHONE_NUM": phone_num,
        "IN_DATE": in_date, "GROUP_IN_DATE": group_in_date, "NATIONALITY": nationality,
        "ADDRESS": address, "CURRENT_EMP_YN": "Y", "OUT_DATE": None
    })

emp_df = pd.DataFrame(initial_employees)
emp_df['IN_DATE'] = pd.to_datetime(emp_df['IN_DATE'])
emp_df['GROUP_IN_DATE'] = pd.to_datetime(emp_df['GROUP_IN_DATE'])

# --- 3. 2단계: 근속 연수에 따라 퇴사자 재선정 및 정보 업데이트 ---
emp_df['TENURE_YEARS'] = (today_ts - emp_df['IN_DATE']).dt.days / 365.25
def get_leaving_probability(tenure):
    base_prob = 0.10
    per_year_increase = 0.06
    max_prob = 0.80
    prob = base_prob + (tenure * per_year_increase)
    return min(prob, max_prob)
emp_df['LEAVING_PROB'] = emp_df['TENURE_YEARS'].apply(get_leaving_probability)
is_leaver_mask = np.random.rand(len(emp_df)) < emp_df['LEAVING_PROB']
emp_df.loc[is_leaver_mask, 'CURRENT_EMP_YN'] = 'N'

def generate_out_date(row):
    if row['CURRENT_EMP_YN'] == 'N':
        min_tenure_days = 30
        total_tenure_days = (today - row['IN_DATE'].date()).days
        if total_tenure_days < min_tenure_days:
            return today
        random_leaving_day = random.randint(min_tenure_days, total_tenure_days)
        return row['IN_DATE'].date() + timedelta(days=random_leaving_day)
    return None
emp_df['OUT_DATE'] = emp_df.apply(generate_out_date, axis=1)
emp_df['OUT_DATE'] = pd.to_datetime(emp_df['OUT_DATE'], errors='coerce')

# --- 4. 최종 컬럼(DURATION, PROB_YN) 계산 ---
emp_df['DURATION'] = (emp_df['OUT_DATE'].fillna(today_ts) - emp_df['IN_DATE']).dt.days
emp_df['PROB_YN'] = np.where((today_ts - emp_df['IN_DATE']).dt.days <= 90, 'Y', 'N')
emp_df = emp_df.drop(columns=['TENURE_YEARS', 'LEAVING_PROB'])

# --- 5. 원본 DataFrame (분석용) ---
emp_df['DURATION'] = emp_df['DURATION'].astype(int)

# --- 6. Google Sheets용 복사본 생성 및 가공 ---
emp_df_for_gsheet = emp_df.copy()
date_cols = ['IN_DATE', 'GROUP_IN_DATE', 'OUT_DATE']
for col in date_cols:
    emp_df_for_gsheet[col] = emp_df_for_gsheet[col].dt.strftime('%Y-%m-%d')
for col in emp_df_for_gsheet.columns:
    emp_df_for_gsheet[col] = emp_df_for_gsheet[col].astype(str)
emp_df_for_gsheet = emp_df_for_gsheet.replace({'None': '', 'nan': '', 'NaT': ''})


# In[ ]:




