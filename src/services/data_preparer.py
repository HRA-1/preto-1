import pandas as pd
import numpy as np
import streamlit as st
import datetime
from datetime import date

# 데이터 로더 및 헬퍼 함수 임포트
from services.data_loader import load_all_base_data
from services.helpers.utils import (
    find_parents, calculate_age, get_level1_ancestor, 
    get_level2_ancestor, find_division_name_for_dept, get_period_dates
)

# 순서 정보 임포트 (view 모듈은 master data의 순서 정보만 import)
from services.tables.HR_Core.department_table import division_order, office_order
from services.tables.HR_Core.job_table import job_l1_order, job_l2_order
from services.tables.HR_Core.position_table import position_order

# --------------------------------------------------------------------------
# --- 순서 정보 ---
# --------------------------------------------------------------------------

age_bins = [-1, 19, 29, 39, 49, 150]
career_bins = [-1, 1, 3, 7, 15, 150]
salary_bins = [-1, 39999999, 59999999, 79999999, 99999999, float('inf')]

age_labels = ['20세 미만', '20-29세', '30-39세', '40-49세', '50세 이상']
career_labels = ['1년 미만', '1~3년', '3~7년', '7~15년', '15년 이상']
salary_labels = ['4,000만원 미만', '4,000~5,999만원', '6,000~7,999만원', '8,000~9,999만원', '1억원 이상']

gender_order = ['남성', '여성']
region_order = ['서울 본사', '국내 현장', '해외 현장']
contract_order = ['정규직', '계약직']

tenure_bins_agg = [-np.inf, 3, 7, np.inf]
tenure_labels_agg = ['3년 이하', '3년초과~7년이하', '7년 초과']

# 모든 순서 정보를 하나의 딕셔너리로 통합
order_map = {
    'DIVISION_NAME': division_order,
    'OFFICE_NAME': office_order,
    'JOB_L1_NAME': job_l1_order,
    'JOB_L2_NAME': job_l2_order,
    'POSITION_NAME': position_order,
    'GENDER': gender_order,
    'AGE_BIN': age_labels,
    'CAREER_BIN': career_labels,
    'SALARY_BIN': salary_labels,
    'REGION_CATEGORY': region_order,
    'CONT_CATEGORY': contract_order,
    'TENURE_GROUP': tenure_labels_agg,
}

# --------------------------------------------------------------------------
# --- 내부 공통 헬퍼 함수 ---
# --------------------------------------------------------------------------

@st.cache_data
def _get_current_employee_snapshot():
    """
    현재 시점의 재직자(Y)에 대한 모든 최신 정보(소속, 직위, 직무, 성별, 연령,
    근속년수, 총 경력, 연봉 등)를 결합하여, 모든 글로벌 필터의 기준이 될 수 있는
    상세한 스냅샷 데이터프레임을 생성합니다.
    """
    # 1. 필요한 모든 기본 데이터 로드
    base_data = load_all_base_data()
    emp_df = base_data["emp_df"]
    position_info_df = base_data["position_info_df"]
    department_info_df = base_data["department_info_df"]
    job_info_df = base_data["job_info_df"]
    career_info_df = base_data["career_info_df"]
    salary_contract_info_df = base_data["salary_contract_info_df"]
    position_df = base_data["position_df"]
    job_df = base_data["job_df"]
    department_df = base_data["department_df"]
    contract_info_df = base_data["contract_info_df"]
    region_df = base_data["region_df"]
    region_info_df = base_data["region_info_df"]

    # 헬퍼 데이터 준비
    job_df_indexed = job_df.set_index('JOB_ID')
    parent_map_job = job_df_indexed['UP_JOB_ID'].to_dict()
    job_name_map = job_df.set_index('JOB_ID')['JOB_NAME'].to_dict()
    dept_level_map = department_df.set_index('DEP_ID')['DEP_LEVEL'].to_dict()
    parent_map_dept = department_df.set_index('DEP_ID')['UP_DEP_ID'].to_dict()
    dept_name_map = department_df.set_index('DEP_ID')['DEP_NAME'].to_dict()

    # 2. 현재 재직자 필터링 및 기본 정보 계산
    snapshot_df = emp_df[emp_df['CURRENT_EMP_YN'] == 'Y'].copy()
    snapshot_df['AGE'] = snapshot_df['PERSONAL_ID'].apply(calculate_age)
    snapshot_df['TENURE_YEARS'] = snapshot_df['DURATION'] / 365.25

    # 3. 현재 소속, 직위, 직무, 연봉 정보 가져오기
    current_depts = department_info_df[department_info_df['DEP_APP_END_DATE'].isnull()][['EMP_ID', 'DEP_ID']]
    current_positions = position_info_df[position_info_df['GRADE_END_DATE'].isnull()][['EMP_ID', 'POSITION_ID', 'GRADE_ID']]
    current_jobs = job_info_df[job_info_df['JOB_APP_END_DATE'].isnull()][['EMP_ID', 'JOB_ID']]
    current_contracts = contract_info_df.sort_values('CONT_START_DATE').groupby('EMP_ID').last().reset_index()
    current_salaries = salary_contract_info_df.sort_values('SAL_START_DATE').groupby('EMP_ID').last().reset_index()
    current_region = region_info_df.sort_values('REG_APP_START_DATE').groupby('EMP_ID').last().reset_index()
    
    # 4. 과거 총 경력 계산
    prior_career_summary = career_info_df.groupby('EMP_ID')['CAREER_DURATION'].sum().reset_index()
    prior_career_summary['TOTAL_PRIOR_CAREER_YEARS'] = prior_career_summary['CAREER_DURATION'] / 365.25

    # 5. 모든 정보 병합
    snapshot_df = pd.merge(snapshot_df, current_depts[['EMP_ID', 'DEP_ID']], on='EMP_ID', how='left')
    snapshot_df = pd.merge(snapshot_df, current_positions[['EMP_ID', 'POSITION_ID', 'GRADE_ID']], on='EMP_ID', how='left')
    snapshot_df = pd.merge(snapshot_df, current_jobs[['EMP_ID', 'JOB_ID']], on='EMP_ID', how='left')
    snapshot_df = pd.merge(snapshot_df, current_contracts[['EMP_ID', 'CONT_CATEGORY']], on='EMP_ID', how='left')
    snapshot_df = pd.merge(snapshot_df, current_salaries[['EMP_ID', 'SAL_AMOUNT', 'PAY_CATEGORY']], on='EMP_ID', how='left')
    snapshot_df = pd.merge(snapshot_df, current_region[['EMP_ID', 'REG_ID']], on='EMP_ID', how='left')
    snapshot_df = pd.merge(snapshot_df, prior_career_summary[['EMP_ID', 'TOTAL_PRIOR_CAREER_YEARS']], on='EMP_ID', how='left')
    snapshot_df['TOTAL_PRIOR_CAREER_YEARS'] = snapshot_df['TOTAL_PRIOR_CAREER_YEARS'].fillna(0)
    
    # 6. 이름 정보 등 추가 (Labeling)
    parent_info = snapshot_df['DEP_ID'].apply(lambda x: find_parents(x, dept_level_map, parent_map_dept, dept_name_map))
    snapshot_df = pd.concat([snapshot_df, parent_info.set_index(snapshot_df.index)], axis=1)
    snapshot_df = pd.merge(snapshot_df, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID', how='left')
    snapshot_df['JOB_L1_NAME'] = snapshot_df['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    snapshot_df['JOB_L2_NAME'] = snapshot_df['JOB_ID'].apply(lambda x: job_name_map.get(get_level2_ancestor(x, job_df_indexed, parent_map_job)))

    # 7. 필터링을 위한 구간(Bin) 정보 추가
    # 7-1. 연봉 환산 (주급, 일급, 시급 포함)
    snapshot_df['ANNUAL_SALARY'] = snapshot_df['SAL_AMOUNT']
    snapshot_df.loc[snapshot_df['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = snapshot_df['SAL_AMOUNT'] * 12
    snapshot_df.loc[snapshot_df['PAY_CATEGORY'] == '주급', 'ANNUAL_SALARY'] = snapshot_df['SAL_AMOUNT'] * 52
    snapshot_df.loc[snapshot_df['PAY_CATEGORY'] == '일급', 'ANNUAL_SALARY'] = snapshot_df['SAL_AMOUNT'] * 250
    snapshot_df.loc[snapshot_df['PAY_CATEGORY'] == '시급', 'ANNUAL_SALARY'] = snapshot_df['SAL_AMOUNT'] * 2080

    # 7-2. 각 그룹(Bin) 컬럼 생성
    # 연령대
    snapshot_df['AGE_BIN'] = pd.cut(snapshot_df['AGE'], bins=age_bins, labels=age_labels)

    # REGION_CATEGORY 추가
    snapshot_df = pd.merge(snapshot_df, region_df[['REG_ID', 'REG_NAME', 'DOMESTIC_YN']], on='REG_ID', how='left')
    snapshot_df['REGION_CATEGORY'] = '해외 현장'
    snapshot_df.loc[snapshot_df['DOMESTIC_YN'] == 'Y', 'REGION_CATEGORY'] = '국내 현장'
    snapshot_df.loc[snapshot_df['REG_NAME'] == '서울특별시', 'REGION_CATEGORY'] = '서울 본사'

    # 근속년수
    snapshot_df['TENURE_GROUP'] = pd.cut(snapshot_df['TENURE_YEARS'], bins=tenure_bins_agg, labels=tenure_labels_agg)

    # 총 경력연차
    snapshot_df['TOTAL_CAREER_YEARS'] = snapshot_df['TENURE_YEARS'] + snapshot_df['TOTAL_PRIOR_CAREER_YEARS']
    snapshot_df['CAREER_BIN'] = pd.cut(snapshot_df['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    
    # 연봉 구간
    snapshot_df['SALARY_BIN'] = pd.cut(snapshot_df['ANNUAL_SALARY'], bins=salary_bins, labels=salary_labels, right=False)

    # 7-3. 순서가 중요한 컬럼들을 Categorical 타입으로 변환
    snapshot_df['DIVISION_NAME'] = pd.Categorical(snapshot_df['DIVISION_NAME'], categories=division_order, ordered=True)
    snapshot_df['OFFICE_NAME'] = pd.Categorical(snapshot_df['OFFICE_NAME'], categories=office_order, ordered=True)
    snapshot_df['JOB_L1_NAME'] = pd.Categorical(snapshot_df['JOB_L1_NAME'], categories=job_l1_order, ordered=True)
    snapshot_df['JOB_L2_NAME'] = pd.Categorical(snapshot_df['JOB_L2_NAME'], categories=job_l2_order, ordered=True)
    snapshot_df['POSITION_NAME'] = pd.Categorical(snapshot_df['POSITION_NAME'], categories=position_order, ordered=True)
    
    # Binning으로 생성된 컬럼들도 순서가 있으므로 Categorical로 변환
    snapshot_df['AGE_BIN'] = pd.Categorical(snapshot_df['AGE_BIN'], categories=age_labels, ordered=True)
    snapshot_df['CAREER_BIN'] = pd.Categorical(snapshot_df['CAREER_BIN'], categories=career_labels, ordered=True)
    snapshot_df['SALARY_BIN'] = pd.Categorical(snapshot_df['SALARY_BIN'], categories=salary_labels, ordered=True)

    # 8. 최종 정리
    snapshot_df['GENDER'] = snapshot_df['GENDER'].map({'M': '남성', 'F': '여성'})
    
    return snapshot_df

@st.cache_data
def _get_monthly_employee_state_df():
    """
    과거부터 현재까지 모든 직원의 '모든 월'에 대한 상태 정보(소속, 직무, 직위, 나이 등)를
    계산하여, 시계열 분석의 기반이 되는 마스터 데이터프레임을 생성합니다.
    결과는 캐싱되어 반복 계산을 방지합니다.
    """
    # 1. 필요한 모든 기본 데이터 로드
    base_data = load_all_base_data()
    emp_df = base_data["emp_df"]
    department_info_df = base_data["department_info_df"]
    job_info_df = base_data["job_info_df"]
    position_info_df = base_data["position_info_df"]
    contract_info_df = base_data["contract_info_df"]
    salary_contract_info_df = base_data["salary_contract_info_df"]
    region_info_df = base_data["region_info_df"]
    career_info_df = base_data["career_info_df"]
    department_df = base_data["department_df"]
    job_df = base_data["job_df"]
    position_df = base_data["position_df"]
    region_df = base_data["region_df"]

    # 2. 헬퍼 데이터 및 정렬된 이력 테이블 준비
    job_df_indexed = job_df.set_index('JOB_ID')
    parent_map_job = job_df_indexed['UP_JOB_ID'].to_dict()
    job_name_map = job_df.set_index('JOB_ID')['JOB_NAME'].to_dict()
    dept_level_map = department_df.set_index('DEP_ID')['DEP_LEVEL'].to_dict()
    parent_map_dept = department_df.set_index('DEP_ID')['UP_DEP_ID'].to_dict()
    dept_name_map = department_df.set_index('DEP_ID')['DEP_NAME'].to_dict()

    dept_info_sorted = department_info_df.sort_values('DEP_APP_START_DATE')
    job_info_sorted = job_info_df.sort_values('JOB_APP_START_DATE')
    pos_info_sorted = position_info_df.sort_values('GRADE_START_DATE')
    contract_info_sorted = contract_info_df.sort_values('CONT_START_DATE')
    salary_info_sorted = salary_contract_info_df.sort_values('SAL_START_DATE')
    region_info_sorted = region_info_df.sort_values('REG_APP_START_DATE')

    # 3. 시간의 뼈대(Scaffold) 생성 및 재직 기간 필터링
    start_month = emp_df['IN_DATE'].min().to_period('M').to_timestamp()
    end_month = pd.to_datetime(datetime.datetime.now()).to_period('M').to_timestamp()
    monthly_periods = pd.date_range(start=start_month, end=end_month, freq='MS')

    scaffold_df = pd.DataFrame(
        [(emp_id, period) for emp_id in emp_df['EMP_ID'].unique() for period in monthly_periods],
        columns=['EMP_ID', 'PERIOD_DT']
    )
    analysis_df = pd.merge(scaffold_df, emp_df, on='EMP_ID', how='left')
    analysis_df['PERIOD_END_DT'] = analysis_df['PERIOD_DT'] + pd.offsets.MonthEnd(0)
    analysis_df = analysis_df[
        (analysis_df['IN_DATE'] <= analysis_df['PERIOD_END_DT']) &
        (analysis_df['OUT_DATE'].isnull() | (analysis_df['OUT_DATE'] >= analysis_df['PERIOD_DT']))
    ].copy()

    # 4. 각 월별로 직원의 모든 속성 정보 부여 (merge_asof)
    analysis_df = pd.merge_asof(analysis_df.sort_values('PERIOD_DT'), dept_info_sorted, left_on='PERIOD_DT', right_on='DEP_APP_START_DATE', by='EMP_ID', direction='backward')
    analysis_df = pd.merge_asof(analysis_df.sort_values('PERIOD_DT'), job_info_sorted, left_on='PERIOD_DT', right_on='JOB_APP_START_DATE', by='EMP_ID', direction='backward')
    analysis_df = pd.merge_asof(analysis_df.sort_values('PERIOD_DT'), pos_info_sorted, left_on='PERIOD_DT', right_on='GRADE_START_DATE', by='EMP_ID', direction='backward')
    analysis_df = pd.merge_asof(analysis_df.sort_values('PERIOD_DT'), contract_info_sorted, left_on='PERIOD_DT', right_on='CONT_START_DATE', by='EMP_ID', direction='backward')
    analysis_df = pd.merge_asof(analysis_df.sort_values('PERIOD_DT'), salary_info_sorted, left_on='PERIOD_DT', right_on='SAL_START_DATE', by='EMP_ID', direction='backward')
    analysis_df = pd.merge_asof(analysis_df.sort_values('PERIOD_DT'), region_info_sorted, left_on='PERIOD_DT', right_on='REG_APP_START_DATE', by='EMP_ID', direction='backward')

    # 5. 이름(Label) 정보 추가
    parent_info = analysis_df['DEP_ID'].apply(lambda x: find_parents(x, dept_level_map, parent_map_dept, dept_name_map))
    analysis_df = pd.concat([analysis_df, parent_info.set_index(analysis_df.index)], axis=1)
    analysis_df = pd.merge(analysis_df, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID', how='left')
    analysis_df['JOB_L1_NAME'] = analysis_df['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    
    # 6. 동적 속성(나이, 근속년수 등) 및 그룹(Bin) 정보 계산
    analysis_df['AGE'] = analysis_df.apply(lambda row: calculate_age(row['PERSONAL_ID'], row['PERIOD_END_DT']), axis=1)
    analysis_df['TENURE_YEARS'] = (analysis_df['PERIOD_END_DT'] - analysis_df['IN_DATE']).dt.days / 365.25
    
    prior_career_summary = career_info_df.groupby('EMP_ID')['CAREER_DURATION'].sum() / 365.25
    analysis_df = pd.merge(analysis_df, prior_career_summary.rename('TOTAL_PRIOR_CAREER_YEARS'), on='EMP_ID', how='left')
    analysis_df['TOTAL_PRIOR_CAREER_YEARS'] = analysis_df['TOTAL_PRIOR_CAREER_YEARS'].fillna(0)
    analysis_df['TOTAL_CAREER_YEARS'] = analysis_df['TENURE_YEARS'] + analysis_df['TOTAL_PRIOR_CAREER_YEARS']
    
    # 연봉 환산
    analysis_df['ANNUAL_SALARY'] = analysis_df['SAL_AMOUNT']
    analysis_df.loc[analysis_df['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = analysis_df['SAL_AMOUNT'] * 12
    analysis_df.loc[analysis_df['PAY_CATEGORY'] == '주급', 'ANNUAL_SALARY'] = analysis_df['SAL_AMOUNT'] * 52
    analysis_df.loc[analysis_df['PAY_CATEGORY'] == '일급', 'ANNUAL_SALARY'] = analysis_df['SAL_AMOUNT'] * 250
    analysis_df.loc[analysis_df['PAY_CATEGORY'] == '시급', 'ANNUAL_SALARY'] = analysis_df['SAL_AMOUNT'] * 2080

    # ----- [수정된 부분 시작] -----
    # 지역 카테고리
    # 먼저 region_df에서 필요한 정보를 merge하여 DOMESTIC_YN 컬럼을 가져옵니다.
    analysis_df = pd.merge(analysis_df, region_df[['REG_ID', 'REG_NAME', 'DOMESTIC_YN']], on='REG_ID', how='left')
    
    # 이제 DOMESTIC_YN 컬럼이 있으므로, REGION_CATEGORY를 안전하게 생성할 수 있습니다.
    analysis_df['REGION_CATEGORY'] = '해외 현장'
    analysis_df.loc[analysis_df['DOMESTIC_YN'] == 'Y', 'REGION_CATEGORY'] = '국내 현장'
    analysis_df.loc[analysis_df['REG_NAME'] == '서울특별시', 'REGION_CATEGORY'] = '서울 본사'
    # ----- [수정된 부분 끝] -----
    
    # 성별
    analysis_df['GENDER'] = analysis_df['GENDER'].map({'M': '남성', 'F': '여성'})

    # 7. 필터링을 위한 구간(Bin) 정보 추가
    analysis_df['AGE_BIN'] = pd.cut(analysis_df['AGE'], bins=age_bins, labels=age_labels)
    analysis_df['CAREER_BIN'] = pd.cut(analysis_df['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    analysis_df['SALARY_BIN'] = pd.cut(analysis_df['ANNUAL_SALARY'], bins=salary_bins, labels=salary_labels, right=False)

    # 8. 최종 정리 및 반환
    final_cols = [
        'EMP_ID', 'PERIOD_DT', 'IN_DATE', 'OUT_DATE',
        'DIVISION_NAME', 'JOB_L1_NAME', 'POSITION_NAME', 'GENDER',
        'AGE_BIN', 'CAREER_BIN', 'SALARY_BIN', 'REGION_CATEGORY', 'CONT_CATEGORY'
    ]
    analysis_df = analysis_df[final_cols].dropna(subset=['DIVISION_NAME', 'JOB_L1_NAME', 'POSITION_NAME'])
    
    return analysis_df

# --- 내부 헬퍼 함수: 코호트 데이터 생성 ---
# 이 함수는 prepare_proposal_06_data 내부 또는 외부에 위치할 수 있습니다.
# 재사용성을 위해 외부에 두고 @st.cache_data를 붙이는 것이 더 효율적일 수 있습니다.
@st.cache_data
def _create_cohort_data(df):
    """
    주어진 데이터프레임(EMP_ID, IN_DATE, OUT_DATE 컬럼 필요)에 대한 
    코호트 잔존율 매트릭스를 생성합니다.
    """
    df = df.copy()
    if df.empty:
        return pd.DataFrame()

    today = datetime.datetime.now()
    df['HIRE_YEAR'] = df['IN_DATE'].dt.year
    df['TENURE_YEAR_INDEX'] = np.floor(
        (df['OUT_DATE'].fillna(pd.to_datetime(today)) - df['IN_DATE']).dt.days / 365.25
    ).astype(int)

    cohort_data_list = []
    for _, row in df.iterrows():
        if pd.isna(row['HIRE_YEAR']) or pd.isna(row['TENURE_YEAR_INDEX']): continue
        for i in range(row['TENURE_YEAR_INDEX'] + 1):
            cohort_data_list.append({
                'HIRE_YEAR': int(row['HIRE_YEAR']), 'TENURE_YEAR': i, 'EMP_ID': row['EMP_ID']
            })

    if not cohort_data_list: return pd.DataFrame()

    cohort_df = pd.DataFrame(cohort_data_list)
    cohort_counts = cohort_df.groupby(['HIRE_YEAR', 'TENURE_YEAR'])['EMP_ID'].nunique().unstack()
    
    if cohort_counts.empty or 0 not in cohort_counts.columns: return pd.DataFrame()

    cohort_sizes = cohort_counts.iloc[:, 0]
    cohort_retention = cohort_counts.divide(cohort_sizes, axis=0) * 100

    current_year = today.year
    for hire_year in cohort_retention.index:
        max_completed_tenure = current_year - hire_year - 1
        if max_completed_tenure < 0:
             cohort_retention.loc[hire_year, cohort_retention.columns > 0] = np.nan
        else:
             cohort_retention.loc[hire_year, cohort_retention.columns > max_completed_tenure] = np.nan

    return cohort_retention

# --------------------------------------------------------------------------
# --- Proposal별 데이터 준비 함수 ---
# --------------------------------------------------------------------------

# 여기에 각 proposal에 필요한 데이터 준비 함수들을 추가합니다.

@st.cache_data
def prepare_basic_proposal_data(
    filter_division='전체',
    filter_job_l1='전체',
    filter_position='전체',
    filter_gender='전체',
    filter_age_bin='전체',
    filter_career_bin='전체',
    filter_salary_bin='전체',
    filter_region='전체',
    filter_contract='전체'
):
    """
    제안 0: 기본 인원 변동 현황
    글로벌 필터를 적용하여, 모든 차원의 월별/분기별/연간 입사, 퇴사, 총원 데이터를 생성합니다.
    """
    # 1. 필요한 모든 기본 데이터 로드
    base_data = load_all_base_data()
    emp_df = base_data["emp_df"]
    department_info_df = base_data["department_info_df"]
    job_info_df = base_data["job_info_df"]
    position_info_df = base_data["position_info_df"]
    career_info_df = base_data["career_info_df"]
    salary_contract_info_df = base_data["salary_contract_info_df"]
    region_info_df = base_data["region_info_df"]
    contract_info_df = base_data["contract_info_df"]
    department_df = base_data["department_df"]
    job_df = base_data["job_df"]
    position_df = base_data["position_df"]
    region_df = base_data["region_df"]

    # 2. 글로벌 필터링을 위한 마스터 직원 테이블 생성
    emp_details = emp_df[['EMP_ID', 'GENDER', 'PERSONAL_ID', 'DURATION', 'IN_DATE', 'OUT_DATE']].copy()
    emp_details['GENDER'] = emp_details['GENDER'].map({'M': '남성', 'F': '여성'})
    emp_details['AGE'] = emp_details['PERSONAL_ID'].apply(calculate_age)
    emp_details['TENURE_YEARS'] = emp_details['DURATION'] / 365.25
    
    first_dept = department_info_df.sort_values('DEP_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_job = job_info_df.sort_values('JOB_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_pos = position_info_df.sort_values('GRADE_START_DATE').groupby('EMP_ID').first().reset_index()
    last_contract = contract_info_df.sort_values('CONT_START_DATE').groupby('EMP_ID').last().reset_index()
    last_region = region_info_df.sort_values('REG_APP_START_DATE').groupby('EMP_ID').last().reset_index()
    last_salary = salary_contract_info_df.sort_values('SAL_START_DATE').groupby('EMP_ID').last().reset_index()
    prior_career_summary = career_info_df.groupby('EMP_ID')['CAREER_DURATION'].sum() / 365.25

    dept_level_map = department_df.set_index('DEP_ID')['DEP_LEVEL'].to_dict()
    parent_map_dept = department_df.set_index('DEP_ID')['UP_DEP_ID'].to_dict()
    dept_name_map = department_df.set_index('DEP_ID')['DEP_NAME'].to_dict()
    job_df_indexed = job_df.set_index('JOB_ID')
    parent_map_job = job_df_indexed['UP_JOB_ID'].to_dict()
    job_name_map = job_df.set_index('JOB_ID')['JOB_NAME'].to_dict()

    first_dept['DIVISION_NAME'] = first_dept['DEP_ID'].apply(lambda x: find_division_name_for_dept(x, dept_level_map, parent_map_dept, dept_name_map))
    first_job['JOB_L1_NAME'] = first_job['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    first_pos = pd.merge(first_pos, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID')
    last_region = pd.merge(last_region, region_df[['REG_ID', 'REG_NAME', 'DOMESTIC_YN']], on='REG_ID', how='left')
    last_region['REGION_CATEGORY'] = '해외 현장'; last_region.loc[last_region['DOMESTIC_YN'] == 'Y', 'REGION_CATEGORY'] = '국내 현장'; last_region.loc[last_region['REG_NAME'] == '서울특별시', 'REGION_CATEGORY'] = '서울 본사'

    emp_details = pd.merge(emp_details, first_dept[['EMP_ID', 'DIVISION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_job[['EMP_ID', 'JOB_L1_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_pos[['EMP_ID', 'POSITION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_contract[['EMP_ID', 'CONT_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_region[['EMP_ID', 'REGION_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_salary[['EMP_ID', 'SAL_AMOUNT', 'PAY_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, prior_career_summary.rename('TOTAL_PRIOR_CAREER_YEARS'), on='EMP_ID', how='left')
    emp_details['TOTAL_PRIOR_CAREER_YEARS'] = emp_details['TOTAL_PRIOR_CAREER_YEARS'].fillna(0)
    emp_details['TOTAL_CAREER_YEARS'] = emp_details['TENURE_YEARS'] + emp_details['TOTAL_PRIOR_CAREER_YEARS']
    
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    emp_details['SALARY_BIN'] = pd.cut(emp_details['ANNUAL_SALARY'], bins=salary_bins, labels=salary_labels, right=False)

    # 3. 글로벌 필터 적용
    filtered_emps_df = emp_details.copy()
    if filter_division != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['DIVISION_NAME'] == filter_division]
    if filter_job_l1 != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['JOB_L1_NAME'] == filter_job_l1]
    if filter_position != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['POSITION_NAME'] == filter_position]
    if filter_gender != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['GENDER'] == filter_gender]
    if filter_age_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['AGE_BIN'] == filter_age_bin]
    if filter_career_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CAREER_BIN'] == filter_career_bin]
    if filter_salary_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['SALARY_BIN'] == filter_salary_bin]
    if filter_region != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['REGION_CATEGORY'] == filter_region]
    if filter_contract != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CONT_CATEGORY'] == filter_contract]
    
    filtered_emp_ids = filtered_emps_df['EMP_ID'].unique()
    if len(filtered_emp_ids) == 0:
        return {}

    # 4. 각 지표를 직접 소스에서 계산
    
    # 4-1. 입사자(Hires) 데이터 준비 및 보강
    # 원본 emp_df에서는 최소 정보만 가져오고, 모든 속성은 emp_details에서 병합
    hires_df = emp_df[emp_df['EMP_ID'].isin(filtered_emp_ids)][['EMP_ID', 'IN_DATE']].copy()
    hires_df['PERIOD_DT'] = hires_df['IN_DATE'].dt.to_period('M').dt.to_timestamp()
    hires_df = pd.merge(hires_df, emp_details.drop(columns=['IN_DATE', 'OUT_DATE', 'DURATION', 'PERSONAL_ID']), on='EMP_ID', how='left')

    # 4-2. 퇴사자(Leavers) 데이터 준비 및 보강
    leavers_df = emp_df[emp_df['EMP_ID'].isin(filtered_emp_ids) & emp_df['OUT_DATE'].notna()][['EMP_ID', 'OUT_DATE']].copy()
    leavers_df['PERIOD_DT'] = leavers_df['OUT_DATE'].dt.to_period('M').dt.to_timestamp()
    leavers_df = pd.merge(leavers_df, emp_details.drop(columns=['IN_DATE', 'OUT_DATE', 'DURATION', 'PERSONAL_ID']), on='EMP_ID', how='left')

    # 4-3. 총원(Headcount) 데이터 준비
    headcount_df = _get_monthly_employee_state_df()
    headcount_df = headcount_df[headcount_df['EMP_ID'].isin(filtered_emp_ids)].copy()
    
    # 5. 각 차원별로 데이터 집계 및 최종 통합
    data_bundle = {}
    dimensions = {
        '부서별': 'DIVISION_NAME', '직무별': 'JOB_L1_NAME', '직위직급별': 'POSITION_NAME',
        '성별': 'GENDER', '연령별': 'AGE_BIN', '경력연차별': 'CAREER_BIN',
        '연봉구간별': 'SALARY_BIN', '지역별': 'REGION_CATEGORY', '계약별': 'CONT_CATEGORY'
    }
    all_dims_to_process = {'전체': None, **dimensions}

    for ui_name, col_name in all_dims_to_process.items():
        grouping_cols = ['PERIOD_DT']
        if col_name: grouping_cols.append(col_name)

        # 각 데이터 소스에서 그룹핑하여 집계
        hires_summary = hires_df.groupby(grouping_cols, observed=False).size().reset_index(name='NEW_HIRES') if not hires_df.empty else pd.DataFrame(columns=grouping_cols + ['NEW_HIRES'])
        leavers_summary = leavers_df.groupby(grouping_cols, observed=False).size().reset_index(name='LEAVERS') if not leavers_df.empty else pd.DataFrame(columns=grouping_cols + ['LEAVERS'])
        headcount_summary = headcount_df.groupby(grouping_cols, observed=False).size().reset_index(name='HEADCOUNT') if not headcount_df.empty else pd.DataFrame(columns=grouping_cols + ['HEADCOUNT'])

        # outer merge로 모든 데이터 통합
        monthly_summary = pd.merge(headcount_summary, hires_summary, on=grouping_cols, how='outer')
        monthly_summary = pd.merge(monthly_summary, leavers_summary, on=grouping_cols, how='outer')
        
        # 숫자형 컬럼에만 fillna(0) 적용 및 타입 변환
        numeric_cols = ['NEW_HIRES', 'LEAVERS', 'HEADCOUNT']
        for col in numeric_cols:
            if col not in monthly_summary.columns: monthly_summary[col] = 0
        monthly_summary[numeric_cols] = monthly_summary[numeric_cols].fillna(0).astype(int)
        
        # 월말 총원이 없는 경우(해당 월 입퇴사) 이전 달 값으로 채우기
        if col_name:
             monthly_summary.sort_values(grouping_cols, inplace=True)
             monthly_summary['HEADCOUNT'] = monthly_summary.groupby(col_name, observed=False)['HEADCOUNT'].transform(lambda x: x.replace(to_replace=0, method='ffill'))
        else:
             monthly_summary.sort_values('PERIOD_DT', inplace=True)
             monthly_summary['HEADCOUNT'] = monthly_summary['HEADCOUNT'].replace(to_replace=0, method='ffill')

        # 분기별/연간 집계
        monthly_summary['QUARTER'] = monthly_summary['PERIOD_DT'].dt.to_period('Q')
        quarterly_summary = monthly_summary.groupby(['QUARTER'] + ([col_name] if col_name else []), observed=False).agg(
            NEW_HIRES=('NEW_HIRES', 'sum'), LEAVERS=('LEAVERS', 'sum'), HEADCOUNT=('HEADCOUNT', 'last')
        ).reset_index()

        monthly_summary['YEAR'] = monthly_summary['PERIOD_DT'].dt.year
        yearly_summary = monthly_summary.groupby(['YEAR'] + ([col_name] if col_name else []), observed=False).agg(
            NEW_HIRES=('NEW_HIRES', 'sum'), LEAVERS=('LEAVERS', 'sum'), HEADCOUNT=('HEADCOUNT', 'last')
        ).reset_index()

        data_bundle[ui_name] = {
            'monthly': monthly_summary,
            'quarterly': quarterly_summary,
            'yearly': yearly_summary
        }
            
    return {
        "data_bundle": data_bundle,
        "order_map": order_map
    }

@st.cache_data
def prepare_proposal_01_data(
    filter_division='전체',
    filter_job_l1='전체',
    filter_position='전체',
    filter_gender='전체',
    filter_age_bin='전체',
    filter_career_bin='전체',
    filter_salary_bin='전체',
    filter_region='전체',
    filter_contract='전체'
):
    """
    제안 1: 조직별/직무별 성장 속도 비교 (승진 소요 기간)
    글로벌 필터를 적용하여 분석 대상을 선정한 뒤, 승진 소요 기간 분석 데이터를 생성합니다.
    """
    # 1. 필요한 모든 기본 데이터 로드
    base_data = load_all_base_data()
    emp_df = base_data["emp_df"]
    position_info_df = base_data["position_info_df"]
    department_info_df = base_data["department_info_df"]
    job_info_df = base_data["job_info_df"]
    career_info_df = base_data["career_info_df"]
    salary_contract_info_df = base_data["salary_contract_info_df"]
    region_info_df = base_data["region_info_df"]
    contract_info_df = base_data["contract_info_df"]
    department_df = base_data["department_df"]
    job_df = base_data["job_df"]
    position_df = base_data["position_df"]
    region_df = base_data["region_df"]

    # 2. 글로벌 필터링을 위한 마스터 직원 테이블 생성 (OFFICE_NAME, JOB_L2_NAME 추가)
    emp_details = emp_df[['EMP_ID', 'GENDER', 'PERSONAL_ID', 'DURATION', 'IN_DATE', 'OUT_DATE']].copy()
    emp_details['GENDER'] = emp_details['GENDER'].map({'M': '남성', 'F': '여성'})
    emp_details['AGE'] = emp_details['PERSONAL_ID'].apply(calculate_age)
    emp_details['TENURE_YEARS'] = emp_details['DURATION'] / 365.25
    
    first_dept = department_info_df.sort_values('DEP_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_job = job_info_df.sort_values('JOB_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_pos = position_info_df.sort_values('GRADE_START_DATE').groupby('EMP_ID').first().reset_index()
    last_contract = contract_info_df.sort_values('CONT_START_DATE').groupby('EMP_ID').last().reset_index()
    last_region = region_info_df.sort_values('REG_APP_START_DATE').groupby('EMP_ID').last().reset_index()
    last_salary = salary_contract_info_df.sort_values('SAL_START_DATE').groupby('EMP_ID').last().reset_index()
    prior_career_summary = career_info_df.groupby('EMP_ID')['CAREER_DURATION'].sum() / 365.25

    dept_level_map = department_df.set_index('DEP_ID')['DEP_LEVEL'].to_dict()
    parent_map_dept = department_df.set_index('DEP_ID')['UP_DEP_ID'].to_dict()
    dept_name_map = department_df.set_index('DEP_ID')['DEP_NAME'].to_dict()
    job_df_indexed = job_df.set_index('JOB_ID')
    parent_map_job = job_df_indexed['UP_JOB_ID'].to_dict()
    job_name_map = job_df.set_index('JOB_ID')['JOB_NAME'].to_dict()

    # find_parents를 사용하여 DIVISION_NAME과 OFFICE_NAME을 한 번에 가져옴
    parent_info = first_dept['DEP_ID'].apply(lambda x: find_parents(x, dept_level_map, parent_map_dept, dept_name_map))
    first_dept = pd.concat([first_dept, parent_info], axis=1)

    # get_level1_ancestor와 get_level2_ancestor를 모두 사용하여 L1, L2 직무명을 가져옴
    first_job['JOB_L1_NAME'] = first_job['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    first_job['JOB_L2_NAME'] = first_job['JOB_ID'].apply(lambda x: job_name_map.get(get_level2_ancestor(x, job_df_indexed, parent_map_job)))
    
    first_pos = pd.merge(first_pos, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID')
    last_region = pd.merge(last_region, region_df[['REG_ID', 'REG_NAME', 'DOMESTIC_YN']], on='REG_ID', how='left')
    last_region['REGION_CATEGORY'] = '해외 현장'; last_region.loc[last_region['DOMESTIC_YN'] == 'Y', 'REGION_CATEGORY'] = '국내 현장'; last_region.loc[last_region['REG_NAME'] == '서울특별시', 'REGION_CATEGORY'] = '서울 본사'

    # 병합할 때 필요한 모든 컬럼을 명시적으로 포함
    emp_details = pd.merge(emp_details, first_dept[['EMP_ID', 'DIVISION_NAME', 'OFFICE_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_job[['EMP_ID', 'JOB_L1_NAME', 'JOB_L2_NAME']], on='EMP_ID', how='left')
    
    emp_details = pd.merge(emp_details, first_pos[['EMP_ID', 'POSITION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_contract[['EMP_ID', 'CONT_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_region[['EMP_ID', 'REGION_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_salary[['EMP_ID', 'SAL_AMOUNT', 'PAY_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, prior_career_summary.rename('TOTAL_PRIOR_CAREER_YEARS'), on='EMP_ID', how='left')
    emp_details['TOTAL_PRIOR_CAREER_YEARS'] = emp_details['TOTAL_PRIOR_CAREER_YEARS'].fillna(0)
    emp_details['TOTAL_CAREER_YEARS'] = emp_details['TENURE_YEARS'] + emp_details['TOTAL_PRIOR_CAREER_YEARS']
    
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    emp_details['SALARY_BIN'] = pd.cut(emp_details['ANNUAL_SALARY'], bins=salary_bins, labels=salary_labels, right=False)

    # 3. 글로벌 필터 적용
    filtered_emps_df = emp_details.copy()
    if filter_division != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['DIVISION_NAME'] == filter_division]
    if filter_job_l1 != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['JOB_L1_NAME'] == filter_job_l1]
    if filter_position != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['POSITION_NAME'] == filter_position]
    if filter_gender != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['GENDER'] == filter_gender]
    if filter_age_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['AGE_BIN'] == filter_age_bin]
    if filter_career_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CAREER_BIN'] == filter_career_bin]
    if filter_salary_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['SALARY_BIN'] == filter_salary_bin]
    if filter_region != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['REGION_CATEGORY'] == filter_region]
    if filter_contract != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CONT_CATEGORY'] == filter_contract]
    
    filtered_emp_ids = filtered_emps_df['EMP_ID'].unique()
    if len(filtered_emp_ids) == 0:
        return {"analysis_df": pd.DataFrame()}

    # 4. 필터링된 직원들만을 대상으로 승진 소요 기간 계산
    pos_info = pd.merge(position_info_df, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID')
    pos_info_filtered = pos_info[pos_info['EMP_ID'].isin(filtered_emp_ids)]
    
    position_start_dates = pos_info_filtered.groupby(['EMP_ID', 'POSITION_NAME'], observed=False)['GRADE_START_DATE'].min().unstack()

    if 'Staff' in position_start_dates.columns and 'Manager' in position_start_dates.columns:
        position_start_dates['TIME_TO_MANAGER'] = (position_start_dates['Manager'] - position_start_dates['Staff']).dt.days / 365.25
    else:
        position_start_dates['TIME_TO_MANAGER'] = np.nan
        
    if 'Manager' in position_start_dates.columns and 'Director' in position_start_dates.columns:
        position_start_dates['TIME_TO_DIRECTOR'] = (position_start_dates['Director'] - position_start_dates['Manager']).dt.days / 365.25
    else:
        position_start_dates['TIME_TO_DIRECTOR'] = np.nan
        
    promo_speed_df = position_start_dates.reset_index()

    # 5. 분석용 데이터프레임 최종 생성
    analysis_df = pd.merge(promo_speed_df, filtered_emps_df, on='EMP_ID', how='inner')
    analysis_df = analysis_df.dropna(subset=['DIVISION_NAME', 'JOB_L1_NAME'])
    
    return {
        "analysis_df": analysis_df,
        "order_map": order_map # 순서 정보를 함께 반환
    }

@st.cache_data
def prepare_proposal_02_data(
    filter_division='전체',
    filter_job_l1='전체',
    filter_position='전체',
    filter_gender='전체',
    filter_age_bin='전체',
    filter_career_bin='전체',
    filter_salary_bin='전체',
    filter_region='전체',
    filter_contract='전체'
):
    """
    제안 2: 차세대 리더 승진 경로 분석 (생키 다이어그램)
    글로벌 필터를 적용하여 분석 대상을 선정한 뒤, 승진 경로 데이터를 생성합니다.
    """
    # 1. 필요한 모든 기본 데이터 로드
    base_data = load_all_base_data()
    emp_df = base_data["emp_df"]
    position_info_df = base_data["position_info_df"]
    department_info_df = base_data["department_info_df"]
    job_info_df = base_data["job_info_df"]
    career_info_df = base_data["career_info_df"]
    salary_contract_info_df = base_data["salary_contract_info_df"]
    region_info_df = base_data["region_info_df"]
    contract_info_df = base_data["contract_info_df"]
    department_df = base_data["department_df"]
    job_df = base_data["job_df"]
    position_df = base_data["position_df"]
    region_df = base_data["region_df"]

    # 2. 글로벌 필터링을 위한 마스터 직원 테이블 생성
    emp_details = emp_df[['EMP_ID', 'GENDER', 'PERSONAL_ID', 'DURATION', 'IN_DATE', 'OUT_DATE']].copy()
    emp_details['GENDER'] = emp_details['GENDER'].map({'M': '남성', 'F': '여성'})
    emp_details['AGE'] = emp_details['PERSONAL_ID'].apply(calculate_age)
    emp_details['TENURE_YEARS'] = emp_details['DURATION'] / 365.25
    
    first_dept = department_info_df.sort_values('DEP_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_job = job_info_df.sort_values('JOB_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_pos = position_info_df.sort_values('GRADE_START_DATE').groupby('EMP_ID').first().reset_index()
    last_contract = contract_info_df.sort_values('CONT_START_DATE').groupby('EMP_ID').last().reset_index()
    last_region = region_info_df.sort_values('REG_APP_START_DATE').groupby('EMP_ID').last().reset_index()
    last_salary = salary_contract_info_df.sort_values('SAL_START_DATE').groupby('EMP_ID').last().reset_index()
    prior_career_summary = career_info_df.groupby('EMP_ID')['CAREER_DURATION'].sum() / 365.25

    dept_level_map = department_df.set_index('DEP_ID')['DEP_LEVEL'].to_dict()
    parent_map_dept = department_df.set_index('DEP_ID')['UP_DEP_ID'].to_dict()
    dept_name_map = department_df.set_index('DEP_ID')['DEP_NAME'].to_dict()
    job_df_indexed = job_df.set_index('JOB_ID')
    parent_map_job = job_df_indexed['UP_JOB_ID'].to_dict()
    job_name_map = job_df.set_index('JOB_ID')['JOB_NAME'].to_dict()

    first_dept['DIVISION_NAME'] = first_dept['DEP_ID'].apply(lambda x: find_division_name_for_dept(x, dept_level_map, parent_map_dept, dept_name_map))
    first_job['JOB_L1_NAME'] = first_job['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    first_pos = pd.merge(first_pos, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID')
    last_region = pd.merge(last_region, region_df[['REG_ID', 'REG_NAME', 'DOMESTIC_YN']], on='REG_ID', how='left')
    last_region['REGION_CATEGORY'] = '해외 현장'; last_region.loc[last_region['DOMESTIC_YN'] == 'Y', 'REGION_CATEGORY'] = '국내 현장'; last_region.loc[last_region['REG_NAME'] == '서울특별시', 'REGION_CATEGORY'] = '서울 본사'
    
    emp_details = pd.merge(emp_details, first_dept[['EMP_ID', 'DIVISION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_job[['EMP_ID', 'JOB_L1_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_pos[['EMP_ID', 'POSITION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_contract[['EMP_ID', 'CONT_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_region[['EMP_ID', 'REGION_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_salary[['EMP_ID', 'SAL_AMOUNT', 'PAY_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, prior_career_summary.rename('TOTAL_PRIOR_CAREER_YEARS'), on='EMP_ID', how='left')
    emp_details['TOTAL_PRIOR_CAREER_YEARS'] = emp_details['TOTAL_PRIOR_CAREER_YEARS'].fillna(0)
    emp_details['TOTAL_CAREER_YEARS'] = emp_details['TENURE_YEARS'] + emp_details['TOTAL_PRIOR_CAREER_YEARS']
    
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    emp_details['SALARY_BIN'] = pd.cut(emp_details['ANNUAL_SALARY'], bins=salary_bins, labels=salary_labels, right=False)

    # 3. 글로벌 필터 적용
    filtered_emps_df = emp_details.copy()
    if filter_division != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['DIVISION_NAME'] == filter_division]
    if filter_job_l1 != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['JOB_L1_NAME'] == filter_job_l1]
    if filter_position != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['POSITION_NAME'] == filter_position]
    if filter_gender != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['GENDER'] == filter_gender]
    if filter_age_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['AGE_BIN'] == filter_age_bin]
    if filter_career_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CAREER_BIN'] == filter_career_bin]
    if filter_salary_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['SALARY_BIN'] == filter_salary_bin]
    if filter_region != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['REGION_CATEGORY'] == filter_region]
    if filter_contract != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CONT_CATEGORY'] == filter_contract]
    
    filtered_emp_ids = filtered_emps_df['EMP_ID'].unique()
    if len(filtered_emp_ids) == 0:
        return {}

    # 4. 필터링된 직원 대상 승진 경로 분석
    pos_info = pd.merge(position_info_df, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID')
    dept_info_sorted = department_info_df.sort_values(['EMP_ID', 'DEP_APP_START_DATE'])
    job_info_sorted = job_info_df.sort_values(['EMP_ID', 'JOB_APP_START_DATE'])
    job_l1_map = job_df[job_df['JOB_LEVEL'] == 1].set_index('JOB_ID')['JOB_NAME'].to_dict()

    def get_promotion_path(employee_id, promotion_to):
        emp_pos_history = pos_info[pos_info['EMP_ID'] == employee_id].sort_values('GRADE_START_DATE')
        promo_event_df = emp_pos_history[emp_pos_history['POSITION_NAME'] == promotion_to]
        if promo_event_df.empty: return None
        promo_event = promo_event_df.iloc[0]

        prev_pos_name = 'Staff' if promotion_to == 'Manager' else 'Manager'
        prev_pos_events = emp_pos_history[(emp_pos_history['POSITION_NAME'] == prev_pos_name) & (emp_pos_history['GRADE_START_DATE'] < promo_event['GRADE_START_DATE'])]
        if prev_pos_events.empty: return None
        
        prev_pos_event_date = prev_pos_events.iloc[-1]['GRADE_START_DATE']
        promo_event_date = promo_event['GRADE_START_DATE']

        emp_dept_history = dept_info_sorted[dept_info_sorted['EMP_ID'] == employee_id]
        emp_job_history = job_info_sorted[job_info_sorted['EMP_ID'] == employee_id]
        
        dept_before_df = emp_dept_history[emp_dept_history['DEP_APP_START_DATE'] <= prev_pos_event_date]
        dept_after_df = emp_dept_history[emp_dept_history['DEP_APP_START_DATE'] <= promo_event_date]
        job_before_df = emp_job_history[emp_job_history['JOB_APP_START_DATE'] <= prev_pos_event_date]
        job_after_df = emp_job_history[emp_job_history['JOB_APP_START_DATE'] <= promo_event_date]

        if any(df.empty for df in [dept_before_df, dept_after_df, job_before_df, job_after_df]): return None
        
        div_before = find_division_name_for_dept(dept_before_df.iloc[-1]['DEP_ID'], dept_level_map, parent_map_dept, dept_name_map)
        div_after = find_division_name_for_dept(dept_after_df.iloc[-1]['DEP_ID'], dept_level_map, parent_map_dept, dept_name_map)
        job_l1_before = job_l1_map.get(get_level1_ancestor(job_before_df.iloc[-1]['JOB_ID'], job_df_indexed, parent_map_job))
        job_l1_after = job_l1_map.get(get_level1_ancestor(job_after_df.iloc[-1]['JOB_ID'], job_df_indexed, parent_map_job))

        if all([div_before, div_after, job_l1_before, job_l1_after]):
            return {
                "from_div": f"{div_before} ({prev_pos_name})", "to_div": f"{div_after} ({promotion_to})",
                "from_job": f"{job_l1_before} ({prev_pos_name})", "to_job": f"{job_l1_after} ({promotion_to})",
            }
        return None

    all_transitions = []
    manager_ids = pos_info[(pos_info['POSITION_NAME'] == 'Manager') & (pos_info['EMP_ID'].isin(filtered_emp_ids))]['EMP_ID'].unique()
    director_ids = pos_info[(pos_info['POSITION_NAME'] == 'Director') & (pos_info['EMP_ID'].isin(filtered_emp_ids))]['EMP_ID'].unique()

    for emp_id in manager_ids:
        path = get_promotion_path(emp_id, 'Manager')
        if path: all_transitions.append(path)
    for emp_id in director_ids:
        path = get_promotion_path(emp_id, 'Director')
        if path: all_transitions.append(path)

    if not all_transitions:
        return {}

    transitions_df = pd.DataFrame(all_transitions)
    
    # Division Sankey 데이터
    sankey_div = transitions_df.groupby(['from_div', 'to_div']).size().reset_index(name='value')
    all_div_nodes_unsorted = pd.concat([sankey_div['from_div'], sankey_div['to_div']]).unique()
    div_map = {f"{div} ({pos})": i for i, div in enumerate(division_order) for pos in ['Staff', 'Manager', 'Director']}
    labels_div = sorted(all_div_nodes_unsorted, key=lambda x: div_map.get(x, 99))
    indices_div = {label: i for i, label in enumerate(labels_div)}

    # Job Sankey 데이터
    sankey_job = transitions_df.groupby(['from_job', 'to_job']).size().reset_index(name='value')
    labels_job = sorted(pd.concat([sankey_job['from_job'], sankey_job['to_job']]).unique())
    indices_job = {label: i for i, label in enumerate(labels_job)}

    # '방식 1'에 따라, view가 사용할 상세 데이터를 반환
    return {
        "sankey_div_data": {"labels": labels_div, "indices": indices_div, "data": sankey_div},
        "sankey_job_data": {"labels": labels_job, "indices": indices_job, "data": sankey_job},
    }

@st.cache_data
def prepare_proposal_03_data(
    filter_division='전체',
    filter_job_l1='전체',
    filter_position='전체',
    filter_gender='전체',
    filter_age_bin='전체',
    filter_career_bin='전체',
    filter_salary_bin='전체',
    filter_region='전체',
    filter_contract='전체'
):
    """
    제안 3: 조직 세대교체 현황 분석 (직위별 연령 분포)
    글로벌 필터를 적용하여 분석 대상을 선정한 뒤, 현재 재직자의 직위별 연령 분포 분석을 위한
    모든 상세 정보를 포함하는 데이터프레임을 생성합니다.
    """
    # 1. 모든 재직자의 최신 정보 스냅샷 로드
    # _get_current_employee_snapshot 함수는 이미 모든 필터링 차원(DIMENSION_CONFIG)에
    # 필요한 컬럼을 포함하고 있습니다.
    snapshot_df = _get_current_employee_snapshot()

    # 2. 글로벌 필터 적용
    analysis_df = snapshot_df.copy()
    if filter_division != '전체': analysis_df = analysis_df[analysis_df['DIVISION_NAME'] == filter_division]
    if filter_job_l1 != '전체': analysis_df = analysis_df[analysis_df['JOB_L1_NAME'] == filter_job_l1]
    if filter_position != '전체': analysis_df = analysis_df[analysis_df['POSITION_NAME'] == filter_position]
    if filter_gender != '전체': analysis_df = analysis_df[analysis_df['GENDER'] == filter_gender]
    if filter_age_bin != '전체': analysis_df = analysis_df[analysis_df['AGE_BIN'] == filter_age_bin]
    if filter_career_bin != '전체': analysis_df = analysis_df[analysis_df['CAREER_BIN'] == filter_career_bin]
    if filter_salary_bin != '전체': analysis_df = analysis_df[analysis_df['SALARY_BIN'] == filter_salary_bin]
    if filter_region != '전체': analysis_df = analysis_df[analysis_df['REGION_CATEGORY'] == filter_region]
    if filter_contract != '전체': analysis_df = analysis_df[analysis_df['CONT_CATEGORY'] == filter_contract]

    # 3. 필터링된 전체 데이터프레임을 그대로 반환
    # view 단에서 이 데이터를 받아 자유롭게 그룹핑하고 시각화할 수 있습니다.
    return {
        "analysis_df": analysis_df,
        "order_map": order_map # 전역 order_map 사용
    }

@st.cache_data
def prepare_proposal_04_data(
    filter_division='전체',
    filter_job_l1='전체',
    filter_position='전체',
    filter_gender='전체',
    filter_age_bin='전체',
    filter_career_bin='전체',
    filter_salary_bin='전체',
    filter_region='전체',
    filter_contract='전체'
):
    """
    제안 4: 조직 경험 자산 현황 (근속년수 분포)
    글로벌 필터를 적용하여 분석 대상을 선정한 뒤, 현재 재직자의 근속년수 분포 분석을 위한
    모든 상세 정보를 포함하는 데이터프레임을 생성합니다.
    """
    # 1. 모든 재직자의 최신 정보 스냅샷 로드
    # _get_current_employee_snapshot 함수는 근속년수(TENURE_YEARS)를 포함한
    # 모든 필터링 차원에 필요한 컬럼을 가지고 있습니다.
    snapshot_df = _get_current_employee_snapshot()

    # 2. 글로벌 필터 적용
    analysis_df = snapshot_df.copy()
    if filter_division != '전체': analysis_df = analysis_df[analysis_df['DIVISION_NAME'] == filter_division]
    if filter_job_l1 != '전체': analysis_df = analysis_df[analysis_df['JOB_L1_NAME'] == filter_job_l1]
    if filter_position != '전체': analysis_df = analysis_df[analysis_df['POSITION_NAME'] == filter_position]
    if filter_gender != '전체': analysis_df = analysis_df[analysis_df['GENDER'] == filter_gender]
    if filter_age_bin != '전체': analysis_df = analysis_df[analysis_df['AGE_BIN'] == filter_age_bin]
    if filter_career_bin != '전체': analysis_df = analysis_df[analysis_df['CAREER_BIN'] == filter_career_bin]
    if filter_salary_bin != '전체': analysis_df = analysis_df[analysis_df['SALARY_BIN'] == filter_salary_bin]
    if filter_region != '전체': analysis_df = analysis_df[analysis_df['REGION_CATEGORY'] == filter_region]
    if filter_contract != '전체': analysis_df = analysis_df[analysis_df['CONT_CATEGORY'] == filter_contract]

    # 3. 필터링된 전체 데이터프레임을 그대로 반환
    # view 단에서 이 데이터를 받아 자유롭게 그룹핑하고 시각화할 수 있습니다.
    return {
        "analysis_df": analysis_df,
        "order_map": order_map # 전역 order_map 사용
    }

@st.cache_data
def prepare_proposal_05_data(
    filter_division='전체',
    filter_job_l1='전체',
    filter_position='전체',
    filter_gender='전체',
    filter_age_bin='전체',
    filter_career_bin='전체',
    filter_salary_bin='전체',
    filter_region='전체',
    filter_contract='전체'
):
    """
    제안 5: 조직 건강도 위험 신호 탐지 (연간 퇴사율)
    모든 차원에 대한 연간 퇴사율을 미리 계산하여 view 함수에 전달합니다.
    """
    # 1. 월별 데이터 및 퇴사자 데이터 로드
    monthly_df = _get_monthly_employee_state_df()
    
    # 2. 글로벌 필터 적용
    analysis_df = monthly_df.copy()
    if filter_division != '전체': analysis_df = analysis_df[analysis_df['DIVISION_NAME'] == filter_division]
    if filter_job_l1 != '전체': analysis_df = analysis_df[analysis_df['JOB_L1_NAME'] == filter_job_l1]
    if filter_position != '전체': analysis_df = analysis_df[analysis_df['POSITION_NAME'] == filter_position]
    if filter_gender != '전체': analysis_df = analysis_df[analysis_df['GENDER'] == filter_gender]
    if filter_age_bin != '전체': analysis_df = analysis_df[analysis_df['AGE_BIN'] == filter_age_bin]
    if filter_career_bin != '전체': analysis_df = analysis_df[analysis_df['CAREER_BIN'] == filter_career_bin]
    if filter_salary_bin != '전체': analysis_df = analysis_df[analysis_df['SALARY_BIN'] == filter_salary_bin]
    if filter_region != '전체': analysis_df = analysis_df[analysis_df['REGION_CATEGORY'] == filter_region]
    if filter_contract != '전체': analysis_df = analysis_df[analysis_df['CONT_CATEGORY'] == filter_contract]

    if analysis_df.empty:
        return {"turnover_data": pd.DataFrame(), "order_map": order_map}

    analysis_df['YEAR'] = analysis_df['PERIOD_DT'].dt.year
    leavers_df = analysis_df[analysis_df['OUT_DATE'].notna()].copy()
    leavers_df = leavers_df.sort_values('PERIOD_DT').groupby('EMP_ID').last().reset_index()
    leavers_df['LEAVER_YEAR'] = leavers_df['OUT_DATE'].dt.year

    # 3. 모든 차원에 대한 퇴사율 계산
    all_dimensions = [
        'DIVISION_NAME', 'OFFICE_NAME', 'JOB_L1_NAME', 'JOB_L2_NAME', 
        'POSITION_NAME', 'GENDER', 'AGE_BIN', 'CAREER_BIN', 
        'SALARY_BIN', 'REGION_CATEGORY', 'CONT_CATEGORY'
    ]
    
    all_turnover_data = []

    # 3. 연도별로 루프를 돌며 계산
    analysis_years = sorted(analysis_df['YEAR'].unique())
    for year in analysis_years:
        
        year_df = analysis_df[analysis_df['YEAR'] == year]
        year_leavers_df = leavers_df[leavers_df['LEAVER_YEAR'] == year]

        # 3-1. '전체' 퇴사율 계산
        # 월별 재직자 수를 센 뒤, 연평균 계산
        monthly_headcount = year_df.groupby('PERIOD_DT')['EMP_ID'].nunique()
        avg_headcount_total = monthly_headcount.mean()
        leavers_count_total = year_leavers_df['EMP_ID'].nunique()
        
        rate = (leavers_count_total / avg_headcount_total) * 100 if avg_headcount_total > 0 else 0
        all_turnover_data.append({'YEAR': year, 'DIMENSION': '전체', 'CATEGORY': '전체', 'TURNOVER_RATE': rate})

        # 3-2. 각 차원별 퇴사율 계산
        for dim in all_dimensions:
            if dim not in year_df.columns: continue

            # 분자: 해당 연도, 해당 차원의 퇴사자 수
            leavers_counts = year_leavers_df.groupby(dim, observed=False)['EMP_ID'].nunique()

            # 분모: 해당 연도, 해당 차원의 월평균 재직자 수
            # pivot_table을 사용하여 더 안전하게 계산
            monthly_pivot = year_df.pivot_table(
                index='PERIOD_DT', 
                columns=dim, 
                values='EMP_ID', 
                aggfunc='nunique',
                observed=False
            )
            avg_headcount = monthly_pivot.mean() # 각 컬럼(카테고리)의 평균을 계산
            
            # 퇴사율 계산
            turnover_rates = (leavers_counts / avg_headcount).fillna(0) * 100
            
            for category, rate in turnover_rates.items():
                if pd.isna(category): continue
                
                record = {'YEAR': year, 'DIMENSION': dim, 'CATEGORY': category, 'TURNOVER_RATE': rate}
                # 드릴다운을 위한 상위 카테고리 정보 추가
                try:
                    if dim == 'OFFICE_NAME':
                        parent_div = year_df[year_df['OFFICE_NAME'] == category]['DIVISION_NAME'].iloc[0]
                        record['PARENT_DIM'] = parent_div
                    elif dim == 'JOB_L2_NAME':
                        parent_job = year_df[year_df['JOB_L2_NAME'] == category]['JOB_L1_NAME'].iloc[0]
                        record['PARENT_DIM'] = parent_job
                except IndexError:
                    # 해당 카테고리에 데이터가 없는 예외적인 경우
                    continue
                
                all_turnover_data.append(record)
    
    # --- [수정된 부분 끝] ---

    final_turnover_df = pd.DataFrame(all_turnover_data)
    final_turnover_df.dropna(subset=['YEAR'], inplace=True)
    final_turnover_df['YEAR'] = final_turnover_df['YEAR'].astype(int)

    return {
        "turnover_data": final_turnover_df,
        "order_map": order_map
    }

@st.cache_data
def prepare_proposal_06_data(
    filter_division='전체',
    filter_job_l1='전체',
    filter_position='전체',
    filter_gender='전체',
    filter_age_bin='전체',
    filter_career_bin='전체',
    filter_salary_bin='전체',
    filter_region='전체',
    filter_contract='전체'
):
    """
    제안 6: 입사 연도별 잔존율 코호트 분석 (모든 차원 지원)
    """
    # 1. 필요한 모든 기본 데이터 로드
    base_data = load_all_base_data()
    emp_df = base_data["emp_df"]
    department_info_df = base_data["department_info_df"]
    job_info_df = base_data["job_info_df"]
    position_info_df = base_data["position_info_df"]
    career_info_df = base_data["career_info_df"]
    salary_contract_info_df = base_data["salary_contract_info_df"]
    region_info_df = base_data["region_info_df"]
    contract_info_df = base_data["contract_info_df"]
    department_df = base_data["department_df"]
    job_df = base_data["job_df"]
    position_df = base_data["position_df"]
    region_df = base_data["region_df"]
    
    # 2. 글로벌 필터링을 위한 마스터 직원 테이블 생성
    emp_details = emp_df[['EMP_ID', 'GENDER', 'PERSONAL_ID', 'DURATION', 'IN_DATE', 'OUT_DATE']].copy()
    emp_details['GENDER'] = emp_details['GENDER'].map({'M': '남성', 'F': '여성'})
    emp_details['AGE'] = emp_details['PERSONAL_ID'].apply(calculate_age)
    emp_details['TENURE_YEARS'] = emp_details['DURATION'] / 365.25
    
    first_dept = department_info_df.sort_values('DEP_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_job = job_info_df.sort_values('JOB_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_pos = position_info_df.sort_values('GRADE_START_DATE').groupby('EMP_ID').first().reset_index()
    last_contract = contract_info_df.sort_values('CONT_START_DATE').groupby('EMP_ID').last().reset_index()
    last_region = region_info_df.sort_values('REG_APP_START_DATE').groupby('EMP_ID').last().reset_index()
    last_salary = salary_contract_info_df.sort_values('SAL_START_DATE').groupby('EMP_ID').last().reset_index()
    prior_career_summary = career_info_df.groupby('EMP_ID')['CAREER_DURATION'].sum() / 365.25

    dept_level_map = department_df.set_index('DEP_ID')['DEP_LEVEL'].to_dict()
    parent_map_dept = department_df.set_index('DEP_ID')['UP_DEP_ID'].to_dict()
    dept_name_map = department_df.set_index('DEP_ID')['DEP_NAME'].to_dict()
    job_df_indexed = job_df.set_index('JOB_ID')
    parent_map_job = job_df_indexed['UP_JOB_ID'].to_dict()
    job_name_map = job_df.set_index('JOB_ID')['JOB_NAME'].to_dict()

    first_dept['DIVISION_NAME'] = first_dept['DEP_ID'].apply(lambda x: find_division_name_for_dept(x, dept_level_map, parent_map_dept, dept_name_map))
    first_job['JOB_L1_NAME'] = first_job['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    first_pos = pd.merge(first_pos, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID')
    last_region = pd.merge(last_region, region_df[['REG_ID', 'REG_NAME', 'DOMESTIC_YN']], on='REG_ID', how='left')
    last_region['REGION_CATEGORY'] = '해외 현장'; last_region.loc[last_region['DOMESTIC_YN'] == 'Y', 'REGION_CATEGORY'] = '국내 현장'; last_region.loc[last_region['REG_NAME'] == '서울특별시', 'REGION_CATEGORY'] = '서울 본사'

    emp_details = pd.merge(emp_details, first_dept[['EMP_ID', 'DIVISION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_job[['EMP_ID', 'JOB_L1_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_pos[['EMP_ID', 'POSITION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_contract[['EMP_ID', 'CONT_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_region[['EMP_ID', 'REGION_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_salary[['EMP_ID', 'SAL_AMOUNT', 'PAY_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, prior_career_summary.rename('TOTAL_PRIOR_CAREER_YEARS'), on='EMP_ID', how='left')
    emp_details['TOTAL_PRIOR_CAREER_YEARS'] = emp_details['TOTAL_PRIOR_CAREER_YEARS'].fillna(0)
    emp_details['TOTAL_CAREER_YEARS'] = emp_details['TENURE_YEARS'] + emp_details['TOTAL_PRIOR_CAREER_YEARS']
    
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    emp_details['SALARY_BIN'] = pd.cut(emp_details['ANNUAL_SALARY'], bins=salary_bins, labels=salary_labels, right=False)

    # 3. 글로벌 필터 적용
    filtered_emps_df = emp_details.copy()
    if filter_division != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['DIVISION_NAME'] == filter_division]
    if filter_job_l1 != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['JOB_L1_NAME'] == filter_job_l1]
    if filter_position != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['POSITION_NAME'] == filter_position]
    if filter_gender != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['GENDER'] == filter_gender]
    if filter_age_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['AGE_BIN'] == filter_age_bin]
    if filter_career_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CAREER_BIN'] == filter_career_bin]
    if filter_salary_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['SALARY_BIN'] == filter_salary_bin]
    if filter_region != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['REGION_CATEGORY'] == filter_region]
    if filter_contract != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CONT_CATEGORY'] == filter_contract]
    
    filtered_emp_ids = filtered_emps_df['EMP_ID'].unique()
    if len(filtered_emp_ids) == 0:
        return {"cohort_data_bundle": {}, "order_map": order_map}
        
    # 4. 필터링된 직원들만을 대상으로 코호트 분석 수행
    analysis_df = emp_df[emp_df['EMP_ID'].isin(filtered_emp_ids)][['EMP_ID', 'IN_DATE', 'OUT_DATE']].copy()
    
    # [수정된 부분] 분석에 필요한 '모든' 차원 정보를 filtered_emps_df로부터 병합
    cols_to_merge = [
        'EMP_ID', 'DIVISION_NAME', 'JOB_L1_NAME', 'POSITION_NAME', 'GENDER', 
        'AGE_BIN', 'CAREER_BIN', 'SALARY_BIN', 'REGION_CATEGORY', 'CONT_CATEGORY'
    ]
    analysis_df = pd.merge(analysis_df, filtered_emps_df[cols_to_merge], on='EMP_ID', how='left')
    
    # 5. 모든 차원별로 코호트 데이터 계산
    cohort_data_bundle = {}
    cohort_data_bundle['전체'] = {
        '전체': _create_cohort_data(analysis_df)
    }
    
    dimensions = {
        '부서별': 'DIVISION_NAME', '직무별': 'JOB_L1_NAME', '직위직급별': 'POSITION_NAME',
        '성별': 'GENDER', '연령별': 'AGE_BIN', '경력연차별': 'CAREER_BIN',
        '연봉구간별': 'SALARY_BIN', '지역별': 'REGION_CATEGORY', '계약별': 'CONT_CATEGORY'
    }

    for dim_ui_name, col_name in dimensions.items():
        if col_name not in analysis_df.columns: continue

        cohort_map = {}
        cohort_map['전체'] = _create_cohort_data(analysis_df)
        
        for category_name in analysis_df[col_name].unique():
            if pd.notna(category_name):
                df_filtered = analysis_df[analysis_df[col_name] == category_name]
                cohort_map[category_name] = _create_cohort_data(df_filtered)
        
        cohort_data_bundle[dim_ui_name] = cohort_map
    
    return {
        "cohort_data_bundle": cohort_data_bundle,
        "order_map": order_map
    }

@st.cache_data
def prepare_proposal_07_data(
    filter_division='전체',
    filter_job_l1='전체',
    filter_position='전체',
    filter_gender='전체',
    filter_age_bin='전체',
    filter_career_bin='전체',
    filter_salary_bin='전체',
    filter_region='전체',
    filter_contract='전체'
):
    """
    제안 7: 경력 유형 및 첫 직무별 재직기간 분석
    글로벌 필터를 적용하여 분석 대상을 선정한 뒤, 재직기간 분석 데이터를 생성합니다.
    """
    # 1. 필요한 모든 기본 데이터 로드
    base_data = load_all_base_data()
    emp_df = base_data["emp_df"]
    department_info_df = base_data["department_info_df"]
    job_info_df = base_data["job_info_df"]
    position_info_df = base_data["position_info_df"]
    career_info_df = base_data["career_info_df"]
    salary_contract_info_df = base_data["salary_contract_info_df"]
    region_info_df = base_data["region_info_df"]
    contract_info_df = base_data["contract_info_df"]
    department_df = base_data["department_df"]
    job_df = base_data["job_df"]
    position_df = base_data["position_df"]
    region_df = base_data["region_df"]

    # 2. 글로벌 필터링을 위한 마스터 직원 테이블 생성
    emp_details = emp_df[['EMP_ID', 'GENDER', 'PERSONAL_ID', 'DURATION', 'IN_DATE', 'OUT_DATE']].copy()
    emp_details['GENDER'] = emp_details['GENDER'].map({'M': '남성', 'F': '여성'})
    emp_details['AGE'] = emp_details['PERSONAL_ID'].apply(calculate_age)
    emp_details['TENURE_YEARS'] = emp_details['DURATION'] / 365.25
    
    first_dept = department_info_df.sort_values('DEP_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_job = job_info_df.sort_values('JOB_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_pos = position_info_df.sort_values('GRADE_START_DATE').groupby('EMP_ID').first().reset_index()
    last_contract = contract_info_df.sort_values('CONT_START_DATE').groupby('EMP_ID').last().reset_index()
    last_region = region_info_df.sort_values('REG_APP_START_DATE').groupby('EMP_ID').last().reset_index()
    last_salary = salary_contract_info_df.sort_values('SAL_START_DATE').groupby('EMP_ID').last().reset_index()
    prior_career_summary = career_info_df.groupby('EMP_ID')['CAREER_DURATION'].sum() / 365.25

    dept_level_map = department_df.set_index('DEP_ID')['DEP_LEVEL'].to_dict()
    parent_map_dept = department_df.set_index('DEP_ID')['UP_DEP_ID'].to_dict()
    dept_name_map = department_df.set_index('DEP_ID')['DEP_NAME'].to_dict()
    job_df_indexed = job_df.set_index('JOB_ID')
    parent_map_job = job_df_indexed['UP_JOB_ID'].to_dict()
    job_name_map = job_df.set_index('JOB_ID')['JOB_NAME'].to_dict()

    first_dept['DIVISION_NAME'] = first_dept['DEP_ID'].apply(lambda x: find_division_name_for_dept(x, dept_level_map, parent_map_dept, dept_name_map))
    first_job['JOB_L1_NAME'] = first_job['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    first_pos = pd.merge(first_pos, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID')
    last_region = pd.merge(last_region, region_df[['REG_ID', 'REG_NAME', 'DOMESTIC_YN']], on='REG_ID', how='left')
    last_region['REGION_CATEGORY'] = '해외 현장'; last_region.loc[last_region['DOMESTIC_YN'] == 'Y', 'REGION_CATEGORY'] = '국내 현장'; last_region.loc[last_region['REG_NAME'] == '서울특별시', 'REGION_CATEGORY'] = '서울 본사'

    emp_details = pd.merge(emp_details, first_dept[['EMP_ID', 'DIVISION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_job[['EMP_ID', 'JOB_L1_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_pos[['EMP_ID', 'POSITION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_contract[['EMP_ID', 'CONT_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_region[['EMP_ID', 'REGION_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_salary[['EMP_ID', 'SAL_AMOUNT', 'PAY_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, prior_career_summary.rename('TOTAL_PRIOR_CAREER_YEARS'), on='EMP_ID', how='left')
    emp_details['TOTAL_PRIOR_CAREER_YEARS'] = emp_details['TOTAL_PRIOR_CAREER_YEARS'].fillna(0)
    emp_details['TOTAL_CAREER_YEARS'] = emp_details['TENURE_YEARS'] + emp_details['TOTAL_PRIOR_CAREER_YEARS']
    
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    emp_details['SALARY_BIN'] = pd.cut(emp_details['ANNUAL_SALARY'], bins=salary_bins, labels=salary_labels, right=False)

    # 3. 글로벌 필터 적용
    filtered_emps_df = emp_details.copy()
    if filter_division != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['DIVISION_NAME'] == filter_division]
    if filter_job_l1 != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['JOB_L1_NAME'] == filter_job_l1]
    if filter_position != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['POSITION_NAME'] == filter_position]
    if filter_gender != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['GENDER'] == filter_gender]
    if filter_age_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['AGE_BIN'] == filter_age_bin]
    if filter_career_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CAREER_BIN'] == filter_career_bin]
    if filter_salary_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['SALARY_BIN'] == filter_salary_bin]
    if filter_region != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['REGION_CATEGORY'] == filter_region]
    if filter_contract != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CONT_CATEGORY'] == filter_contract]
    
    filtered_emp_ids = filtered_emps_df['EMP_ID'].unique()
    if len(filtered_emp_ids) == 0:
        return {"analysis_df": pd.DataFrame(), "order_map": order_map}

    # 4. 필터링된 직원들만을 대상으로 재직기간 분석 데이터 생성
    # 경력 유형 계산
    career_summary = career_info_df[career_info_df['EMP_ID'].isin(filtered_emp_ids)].groupby('EMP_ID')['CAREER_REL_YN'].apply(
        lambda x: '관련 경력' if 'Y' in x.values else '비관련 경력'
    ).reset_index().rename(columns={'CAREER_REL_YN': 'CAREER_TYPE'})
    
    # 분석의 기반이 될 데이터프레임 생성 (필터링된 직원 대상)
    analysis_df = emp_df[emp_df['EMP_ID'].isin(filtered_emp_ids)][['EMP_ID', 'DURATION']].copy()
    analysis_df['TENURE_YEARS'] = analysis_df['DURATION'] / 365.25
    
    # 경력 유형 병합
    analysis_df = pd.merge(analysis_df, career_summary, on='EMP_ID', how='left')
    analysis_df['CAREER_TYPE'] = analysis_df['CAREER_TYPE'].fillna('경력 없음')

    # 분석에 필요한 '모든' 차원 정보를 filtered_emps_df에서 가져옴
    cols_to_merge = [
        'EMP_ID', 'DIVISION_NAME', 'JOB_L1_NAME', 'POSITION_NAME',
        'GENDER', 'AGE_BIN', 'CAREER_BIN', 'SALARY_BIN', 
        'REGION_CATEGORY', 'CONT_CATEGORY'
    ]
    
    # filtered_emps_df에서 필요한 컬럼만 추출 (중복 제거)
    emp_attrs = filtered_emps_df[cols_to_merge].drop_duplicates(subset=['EMP_ID'])
    
    analysis_df = pd.merge(
        analysis_df, 
        emp_attrs.rename(columns={'JOB_L1_NAME':'JOB_CATEGORY'}), 
        on='EMP_ID', 
        how='left'
    )
    
    analysis_df = analysis_df.dropna(subset=['DIVISION_NAME', 'JOB_CATEGORY', 'POSITION_NAME'])

    return {"analysis_df": analysis_df, "order_map": order_map}

@st.cache_data
def prepare_proposal_08_data(
    filter_division='전체',
    filter_job_l1='전체',
    filter_position='전체',
    filter_gender='전체',
    filter_age_bin='전체',
    filter_career_bin='전체',
    filter_salary_bin='전체',
    filter_region='전체',
    filter_contract='전체'
):
    """
    제안 8: 인력 유지 현황 분석 (재직자 vs 퇴사자) - 범용 버전
    글로벌 필터를 적용하여, 모든 차원별 재직/퇴사자 근속년수 분석 데이터를 생성합니다.
    """
    # 1. 필요한 모든 기본 데이터 로드
    base_data = load_all_base_data()
    emp_df = base_data["emp_df"]
    department_info_df = base_data["department_info_df"]
    job_info_df = base_data["job_info_df"]
    position_info_df = base_data["position_info_df"]
    career_info_df = base_data["career_info_df"]
    salary_contract_info_df = base_data["salary_contract_info_df"]
    region_info_df = base_data["region_info_df"]
    contract_info_df = base_data["contract_info_df"]
    department_df = base_data["department_df"]
    job_df = base_data["job_df"]
    position_df = base_data["position_df"]
    region_df = base_data["region_df"]

    # 2. 글로벌 필터링을 위한 마스터 직원 테이블 생성
    # [수정] 'CURRENT_EMP_YN'을 포함하여 모든 직원의 데이터를 가져옴
    emp_details = emp_df[['EMP_ID', 'GENDER', 'PERSONAL_ID', 'DURATION', 'IN_DATE', 'OUT_DATE', 'CURRENT_EMP_YN']].copy()
    emp_details['GENDER'] = emp_details['GENDER'].map({'M': '남성', 'F': '여성'})
    emp_details['AGE'] = emp_details['PERSONAL_ID'].apply(calculate_age)
    emp_details['TENURE_YEARS'] = emp_details['DURATION'] / 365.25
    
    first_dept = department_info_df.sort_values('DEP_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_job = job_info_df.sort_values('JOB_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_pos = position_info_df.sort_values('GRADE_START_DATE').groupby('EMP_ID').first().reset_index()
    last_contract = contract_info_df.sort_values('CONT_START_DATE').groupby('EMP_ID').last().reset_index()
    last_region = region_info_df.sort_values('REG_APP_START_DATE').groupby('EMP_ID').last().reset_index()
    last_salary = salary_contract_info_df.sort_values('SAL_START_DATE').groupby('EMP_ID').last().reset_index()
    prior_career_summary = (career_info_df.groupby('EMP_ID')['CAREER_DURATION'].sum() / 365.25).reset_index(name='TOTAL_PRIOR_CAREER_YEARS')

    dept_level_map = department_df.set_index('DEP_ID')['DEP_LEVEL'].to_dict()
    parent_map_dept = department_df.set_index('DEP_ID')['UP_DEP_ID'].to_dict()
    dept_name_map = department_df.set_index('DEP_ID')['DEP_NAME'].to_dict()
    job_df_indexed = job_df.set_index('JOB_ID')
    parent_map_job = job_df_indexed['UP_JOB_ID'].to_dict()
    job_name_map = job_df.set_index('JOB_ID')['JOB_NAME'].to_dict()
    
    # [수정] find_parents를 사용하여 OFFICE_NAME, JOB_L2_NAME 등 모든 레벨 정보 추가
    parent_info = first_dept['DEP_ID'].apply(lambda x: find_parents(x, dept_level_map, parent_map_dept, dept_name_map))
    first_dept = pd.concat([first_dept, parent_info], axis=1)
    first_job['JOB_L1_NAME'] = first_job['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    first_job['JOB_L2_NAME'] = first_job['JOB_ID'].apply(lambda x: job_name_map.get(get_level2_ancestor(x, job_df_indexed, parent_map_job)))
    first_pos = pd.merge(first_pos, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID')
    last_region = pd.merge(last_region, region_df[['REG_ID', 'REG_NAME', 'DOMESTIC_YN']], on='REG_ID', how='left')
    last_region['REGION_CATEGORY'] = '해외 현장'; last_region.loc[last_region['DOMESTIC_YN'] == 'Y', 'REGION_CATEGORY'] = '국내 현장'; last_region.loc[last_region['REG_NAME'] == '서울특별시', 'REGION_CATEGORY'] = '서울 본사'
    
    emp_details = pd.merge(emp_details, first_dept[['EMP_ID', 'DIVISION_NAME', 'OFFICE_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_job[['EMP_ID', 'JOB_L1_NAME', 'JOB_L2_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_pos[['EMP_ID', 'POSITION_NAME', 'GRADE_ID']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_contract[['EMP_ID', 'CONT_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_region[['EMP_ID', 'REGION_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_salary[['EMP_ID', 'SAL_AMOUNT', 'PAY_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, prior_career_summary, on='EMP_ID', how='left')
    emp_details['TOTAL_PRIOR_CAREER_YEARS'] = emp_details['TOTAL_PRIOR_CAREER_YEARS'].fillna(0)
    emp_details['TOTAL_CAREER_YEARS'] = emp_details['TENURE_YEARS'] + emp_details['TOTAL_PRIOR_CAREER_YEARS']
    
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    emp_details['SALARY_BIN'] = pd.cut(emp_details['ANNUAL_SALARY'], bins=salary_bins, labels=salary_labels, right=False)

    # 3. 글로벌 필터 적용
    filtered_emps_df = emp_details.copy()
    if filter_division != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['DIVISION_NAME'] == filter_division]
    if filter_job_l1 != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['JOB_L1_NAME'] == filter_job_l1]
    if filter_position != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['POSITION_NAME'] == filter_position]
    if filter_gender != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['GENDER'] == filter_gender]
    if filter_age_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['AGE_BIN'] == filter_age_bin]
    if filter_career_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CAREER_BIN'] == filter_career_bin]
    if filter_salary_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['SALARY_BIN'] == filter_salary_bin]
    if filter_region != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['REGION_CATEGORY'] == filter_region]
    if filter_contract != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CONT_CATEGORY'] == filter_contract]
    
    # 4. 최종 analysis_df 생성
    # filtered_emps_df에는 이미 글로벌 필터가 적용되었으며, 
    # 모든 차원(DIMENSION_CONFIG) 컬럼이 포함되어 있음
    analysis_df = filtered_emps_df.copy()
    analysis_df['STATUS'] = np.where(analysis_df['CURRENT_EMP_YN'] == 'Y', '재직자', '퇴사자')
    
    # 분석에 불필요한 컬럼 정리 (선택 사항이나, 깔끔하게 정리)
    analysis_df = analysis_df.drop(columns=['PERSONAL_ID', 'DURATION', 'IN_DATE', 'OUT_DATE'], errors='ignore')

    return {"analysis_df": analysis_df, "order_map": order_map}

@st.cache_data
def prepare_proposal_09_data(
    filter_division='전체',
    filter_job_l1='전체',
    filter_position='전체',
    filter_gender='전체',
    filter_age_bin='전체',
    filter_career_bin='전체',
    filter_salary_bin='전체',
    filter_region='전체',
    filter_contract='전체'
):
    """
    제안 9: 조직 활력도 진단 (연간 직무 이동률) - 단순화 버전
    """
    # 1. 필요한 모든 기본 데이터 로드
    base_data = load_all_base_data()
    emp_df = base_data["emp_df"]
    department_info_df = base_data["department_info_df"]
    job_info_df = base_data["job_info_df"]
    position_info_df = base_data["position_info_df"]
    career_info_df = base_data["career_info_df"]
    salary_contract_info_df = base_data["salary_contract_info_df"]
    region_info_df = base_data["region_info_df"]
    contract_info_df = base_data["contract_info_df"]
    department_df = base_data["department_df"]
    job_df = base_data["job_df"]
    position_df = base_data["position_df"]
    region_df = base_data["region_df"]

    # 2. 글로벌 필터링을 위한 마스터 직원 테이블 생성
    emp_details = emp_df[['EMP_ID', 'GENDER', 'PERSONAL_ID', 'DURATION', 'IN_DATE', 'OUT_DATE']].copy()
    emp_details['GENDER'] = emp_details['GENDER'].map({'M': '남성', 'F': '여성'})
    emp_details['AGE'] = emp_details['PERSONAL_ID'].apply(calculate_age)
    emp_details['TENURE_YEARS'] = emp_details['DURATION'] / 365.25
    
    first_dept = department_info_df.sort_values('DEP_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_job = job_info_df.sort_values('JOB_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_pos = position_info_df.sort_values('GRADE_START_DATE').groupby('EMP_ID').first().reset_index()
    last_contract = contract_info_df.sort_values('CONT_START_DATE').groupby('EMP_ID').last().reset_index()
    last_region = region_info_df.sort_values('REG_APP_START_DATE').groupby('EMP_ID').last().reset_index()
    last_salary = salary_contract_info_df.sort_values('SAL_START_DATE').groupby('EMP_ID').last().reset_index()
    prior_career_summary = career_info_df.groupby('EMP_ID')['CAREER_DURATION'].sum() / 365.25

    dept_level_map = department_df.set_index('DEP_ID')['DEP_LEVEL'].to_dict()
    parent_map_dept = department_df.set_index('DEP_ID')['UP_DEP_ID'].to_dict()
    dept_name_map = department_df.set_index('DEP_ID')['DEP_NAME'].to_dict()
    job_df_indexed = job_df.set_index('JOB_ID')
    parent_map_job = job_df_indexed['UP_JOB_ID'].to_dict()
    job_name_map = job_df.set_index('JOB_ID')['JOB_NAME'].to_dict()

    first_dept['DIVISION_NAME'] = first_dept['DEP_ID'].apply(lambda x: find_division_name_for_dept(x, dept_level_map, parent_map_dept, dept_name_map))
    first_job['JOB_L1_NAME'] = first_job['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    first_pos = pd.merge(first_pos, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID')
    last_region = pd.merge(last_region, region_df[['REG_ID', 'REG_NAME', 'DOMESTIC_YN']], on='REG_ID', how='left')
    last_region['REGION_CATEGORY'] = '해외 현장'; last_region.loc[last_region['DOMESTIC_YN'] == 'Y', 'REGION_CATEGORY'] = '국내 현장'; last_region.loc[last_region['REG_NAME'] == '서울특별시', 'REGION_CATEGORY'] = '서울 본사'
    
    emp_details = pd.merge(emp_details, first_dept[['EMP_ID', 'DIVISION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_job[['EMP_ID', 'JOB_L1_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_pos[['EMP_ID', 'POSITION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_contract[['EMP_ID', 'CONT_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_region[['EMP_ID', 'REGION_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_salary[['EMP_ID', 'SAL_AMOUNT', 'PAY_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, prior_career_summary.rename('TOTAL_PRIOR_CAREER_YEARS'), on='EMP_ID', how='left')
    emp_details['TOTAL_PRIOR_CAREER_YEARS'] = emp_details['TOTAL_PRIOR_CAREER_YEARS'].fillna(0)
    emp_details['TOTAL_CAREER_YEARS'] = emp_details['TENURE_YEARS'] + emp_details['TOTAL_PRIOR_CAREER_YEARS']
    
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    emp_details['SALARY_BIN'] = pd.cut(emp_details['ANNUAL_SALARY'], bins=salary_bins, labels=salary_labels, right=False)

    # 3. 글로벌 필터 적용
    filtered_emps_df = emp_details.copy()
    if filter_division != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['DIVISION_NAME'] == filter_division]
    if filter_job_l1 != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['JOB_L1_NAME'] == filter_job_l1]
    if filter_position != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['POSITION_NAME'] == filter_position]
    if filter_gender != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['GENDER'] == filter_gender]
    if filter_age_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['AGE_BIN'] == filter_age_bin]
    if filter_career_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CAREER_BIN'] == filter_career_bin]
    if filter_salary_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['SALARY_BIN'] == filter_salary_bin]
    if filter_region != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['REGION_CATEGORY'] == filter_region]
    if filter_contract != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CONT_CATEGORY'] == filter_contract]
    
    filtered_emp_ids = filtered_emps_df['EMP_ID'].unique()
    
    if len(filtered_emp_ids) == 0:
        return {"analysis_df": pd.DataFrame(), "overall_df": pd.DataFrame(), "order_map": order_map}

    # 3. 필터링된 직원 대상 연간 직무 이동률 계산
    job_changes = job_info_df[job_info_df['EMP_ID'].isin(filtered_emp_ids)].copy()
    job_changes = pd.merge(job_changes, emp_df[['EMP_ID', 'IN_DATE']], on='EMP_ID', how='left')
    job_changes = job_changes[job_changes['JOB_APP_START_DATE'] > job_changes['IN_DATE']]
    job_changes['YEAR'] = job_changes['JOB_APP_START_DATE'].dt.year

    analysis_records = []
    overall_records = []
    all_years = sorted(job_changes['YEAR'].unique())
    
    # 정렬된 이력 테이블 준비
    dept_info_sorted = department_info_df.sort_values('DEP_APP_START_DATE')
    job_info_sorted = job_info_df.sort_values('JOB_APP_START_DATE')
    pos_info_sorted = position_info_df.sort_values('GRADE_START_DATE')

    for year in all_years:
        year_end = pd.to_datetime(f'{year}-12-31')
        active_in_year_base = emp_df[
            (emp_df['IN_DATE'] <= year_end) & 
            (emp_df['OUT_DATE'].isnull() | (emp_df['OUT_DATE'] > year_end)) & 
            (emp_df['EMP_ID'].isin(filtered_emp_ids))
        ]
        active_in_year = active_in_year_base[['EMP_ID', 'IN_DATE']].copy()
        changes_in_year = job_changes[job_changes['YEAR'] == year][['EMP_ID', 'JOB_APP_START_DATE']].copy()
        
        if active_in_year.empty: continue

        # '전체 평균' 이동률 계산
        overall_rate = (changes_in_year['EMP_ID'].nunique() / active_in_year['EMP_ID'].nunique()) * 100
        overall_records.append({'YEAR': year, 'MOBILITY_RATE': overall_rate})
            
        # 속성 부여에 필요한 데이터프레임 생성
        active_in_year['DATE_SNAPSHOT'] = year_end
        changes_in_year['DATE_SNAPSHOT'] = changes_in_year['JOB_APP_START_DATE']
        
        # 분석에 필요한 속성 정보들을 한 번에 병합
        attrs_to_merge = filtered_emps_df[[
            'EMP_ID', 'DIVISION_NAME', 'JOB_L1_NAME', 'POSITION_NAME', 'GENDER', 
            'AGE_BIN', 'CAREER_BIN', 'SALARY_BIN', 'REGION_CATEGORY', 'CONT_CATEGORY'
        ]].drop_duplicates(subset=['EMP_ID'])

        active_with_attrs = pd.merge(active_in_year, attrs_to_merge, on='EMP_ID', how='left')
        changes_with_attrs = pd.merge(changes_in_year, attrs_to_merge, on='EMP_ID', how='left')

        # 분석할 최상위 차원 목록
        top_level_dimensions = [
            'DIVISION_NAME', 'JOB_L1_NAME', 'POSITION_NAME', 'GENDER', 
            'AGE_BIN', 'CAREER_BIN', 'SALARY_BIN', 'REGION_CATEGORY', 'CONT_CATEGORY'
        ]

        for dim_col in top_level_dimensions:
            if dim_col not in active_with_attrs.columns or dim_col not in changes_with_attrs.columns:
                continue
            
            headcount_grouped = active_with_attrs.dropna(subset=[dim_col]).groupby(dim_col, observed=False)['EMP_ID'].nunique()
            changes_grouped = changes_with_attrs.dropna(subset=[dim_col]).groupby(dim_col, observed=False)['EMP_ID'].nunique()
            mobility_rates = (changes_grouped / headcount_grouped * 100).fillna(0)

            for group_name, rate in mobility_rates.items():
                if pd.isna(group_name): continue
                record = {'YEAR': year, 'GROUP_TYPE': dim_col, 'GROUP_NAME': group_name, 'MOBILITY_RATE': rate}
                analysis_records.append(record)
    
    analysis_df = pd.DataFrame(analysis_records)
    overall_df = pd.DataFrame(overall_records)

    return {"analysis_df": analysis_df, "overall_df": overall_df, "order_map": order_map}

@st.cache_data
def prepare_proposal_10_data(
    filter_division='전체',
    filter_job_l1='전체',
    filter_position='전체',
    filter_gender='전체',
    filter_age_bin='전체',
    filter_career_bin='전체',
    filter_salary_bin='전체',
    filter_region='전체',
    filter_contract='전체'
):
    """
    제안 10: 학력/경력과 초봉의 관계 분석 (구조 개선 최종 버전)
    """
    # 1. 필요한 모든 기본 데이터 로드
    base_data = load_all_base_data()
    emp_df = base_data["emp_df"]
    department_info_df = base_data["department_info_df"]
    job_info_df = base_data["job_info_df"]
    position_info_df = base_data["position_info_df"]
    career_info_df = base_data["career_info_df"]
    salary_contract_info_df = base_data["salary_contract_info_df"]
    region_info_df = base_data["region_info_df"]
    contract_info_df = base_data["contract_info_df"]
    department_df = base_data["department_df"]
    job_df = base_data["job_df"]
    position_df = base_data["position_df"]
    region_df = base_data["region_df"]
    school_info_df = base_data["school_info_df"]
    school_df = base_data["school_df"]

    # 2. 글로벌 필터링을 위한 마스터 직원 테이블 생성
    emp_details = emp_df[['EMP_ID', 'GENDER', 'PERSONAL_ID', 'DURATION', 'IN_DATE', 'OUT_DATE']].copy()
    emp_details['GENDER'] = emp_details['GENDER'].map({'M': '남성', 'F': '여성'})
    emp_details['AGE'] = emp_details['PERSONAL_ID'].apply(calculate_age)
    emp_details['TENURE_YEARS'] = emp_details['DURATION'] / 365.25
    
    first_dept = department_info_df.sort_values('DEP_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_job = job_info_df.sort_values('JOB_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_pos = position_info_df.sort_values('GRADE_START_DATE').groupby('EMP_ID').first().reset_index()
    last_contract = contract_info_df.sort_values('CONT_START_DATE').groupby('EMP_ID').last().reset_index()
    last_region = region_info_df.sort_values('REG_APP_START_DATE').groupby('EMP_ID').last().reset_index()
    last_salary = salary_contract_info_df.sort_values('SAL_START_DATE').groupby('EMP_ID').last().reset_index()
    prior_career_summary = (career_info_df.groupby('EMP_ID')['CAREER_DURATION'].sum() / 365.25).reset_index(name='TOTAL_PRIOR_CAREER_YEARS')

    dept_level_map = department_df.set_index('DEP_ID')['DEP_LEVEL'].to_dict()
    parent_map_dept = department_df.set_index('DEP_ID')['UP_DEP_ID'].to_dict()
    dept_name_map = department_df.set_index('DEP_ID')['DEP_NAME'].to_dict()
    job_df_indexed = job_df.set_index('JOB_ID')
    parent_map_job = job_df_indexed['UP_JOB_ID'].to_dict()
    job_name_map = job_df.set_index('JOB_ID')['JOB_NAME'].to_dict()

    first_dept['DIVISION_NAME'] = first_dept['DEP_ID'].apply(lambda x: find_division_name_for_dept(x, dept_level_map, parent_map_dept, dept_name_map))
    first_job['JOB_L1_NAME'] = first_job['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    first_pos = pd.merge(first_pos, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID')
    last_region = pd.merge(last_region, region_df[['REG_ID', 'REG_NAME', 'DOMESTIC_YN']], on='REG_ID', how='left')
    last_region['REGION_CATEGORY'] = '해외 현장'; last_region.loc[last_region['DOMESTIC_YN'] == 'Y', 'REGION_CATEGORY'] = '국내 현장'; last_region.loc[last_region['REG_NAME'] == '서울특별시', 'REGION_CATEGORY'] = '서울 본사'

    emp_details = pd.merge(emp_details, first_dept[['EMP_ID', 'DIVISION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_job[['EMP_ID', 'JOB_L1_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_pos[['EMP_ID', 'POSITION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_contract[['EMP_ID', 'CONT_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_region[['EMP_ID', 'REGION_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_salary[['EMP_ID', 'SAL_AMOUNT', 'PAY_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, prior_career_summary, on='EMP_ID', how='left')
    emp_details['TOTAL_PRIOR_CAREER_YEARS'] = emp_details['TOTAL_PRIOR_CAREER_YEARS'].fillna(0)
    emp_details['TOTAL_CAREER_YEARS'] = emp_details['TENURE_YEARS'] + emp_details['TOTAL_PRIOR_CAREER_YEARS']
    
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    emp_details['SALARY_BIN'] = pd.cut(emp_details['ANNUAL_SALARY'], bins=salary_bins, labels=salary_labels, right=False)

    # 3. 글로벌 필터 적용
    filtered_emps_df = emp_details.copy()
    if filter_division != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['DIVISION_NAME'] == filter_division]
    if filter_job_l1 != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['JOB_L1_NAME'] == filter_job_l1]
    if filter_position != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['POSITION_NAME'] == filter_position]
    if filter_gender != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['GENDER'] == filter_gender]
    if filter_age_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['AGE_BIN'] == filter_age_bin]
    if filter_career_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CAREER_BIN'] == filter_career_bin]
    if filter_salary_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['SALARY_BIN'] == filter_salary_bin]
    if filter_region != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['REGION_CATEGORY'] == filter_region]
    if filter_contract != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CONT_CATEGORY'] == filter_contract]
    
    filtered_emp_ids = filtered_emps_df['EMP_ID'].unique()
    if len(filtered_emp_ids) == 0:
        return {"analysis_df": pd.DataFrame(), "order_map": order_map}

    # 4. 필터링된 직원들(filtered_emp_ids)을 기준으로, 필요한 정보를 순차적으로 결합
    # 4-1. 초봉 정보 (분석의 시작점)
    initial_contracts = salary_contract_info_df[
        (salary_contract_info_df['PAY_CATEGORY'] == '연봉') &
        (salary_contract_info_df['EMP_ID'].isin(filtered_emp_ids))
    ].sort_values('SAL_START_DATE').groupby('EMP_ID').first().reset_index()
    analysis_df = initial_contracts[['EMP_ID', 'SAL_AMOUNT']].rename(columns={'SAL_AMOUNT': 'INITIAL_SALARY'})

    # 4-2. 최종 학력 정보 병합
    # 필터링된 직원의 학력 이력만 가져옴
    school_history_filtered = school_info_df[school_info_df['EMP_ID'].isin(filtered_emp_ids)].copy()
    
    # 각 직원의 최종 학력 기록을 찾음 (이 테이블에 이미 MAJOR_CATEGORY가 있음)
    final_education = school_history_filtered.sort_values('GRAD_YEAR').groupby('EMP_ID').last().reset_index()
    
    # SCHOOL_LEVEL 정보만 school_df에서 가져와 병합
    final_education = pd.merge(final_education, school_df[['SCHOOL_ID', 'SCHOOL_LEVEL']], on='SCHOOL_ID', how='left')
    
    # 최종적으로 analysis_df에 병합
    analysis_df = pd.merge(analysis_df, final_education[['EMP_ID', 'SCHOOL_LEVEL', 'MAJOR_CATEGORY']], on='EMP_ID', how='left')
    
    # 4-3. 과거 총 경력 정보 병합
    prior_career = career_info_df[career_info_df['EMP_ID'].isin(filtered_emp_ids)].copy()
    if not prior_career.empty:
        prior_career_summary = prior_career.groupby('EMP_ID')['CAREER_DURATION'].sum().reset_index()
        prior_career_summary['TOTAL_PRIOR_CAREER_YEARS'] = prior_career_summary['CAREER_DURATION'] / 365.25
        analysis_df = pd.merge(analysis_df, prior_career_summary[['EMP_ID', 'TOTAL_PRIOR_CAREER_YEARS']], on='EMP_ID', how='left')
    else:
        analysis_df['TOTAL_PRIOR_CAREER_YEARS'] = 0
    
    analysis_df['TOTAL_PRIOR_CAREER_YEARS'] = analysis_df['TOTAL_PRIOR_CAREER_YEARS'].fillna(0)
    
    # 5. 최종 가공 및 반환
    analysis_df = analysis_df.dropna(subset=['INITIAL_SALARY', 'SCHOOL_LEVEL', 'MAJOR_CATEGORY'])
    if analysis_df.empty:
        return {"analysis_df": pd.DataFrame(), "order_map": order_map}

    bins = [-1, 3, 7, 100]
    labels = ['신입 (0~3년)', '주니어 (3~7년)', '시니어 (7년+)']
    analysis_df['CAREER_BIN'] = pd.cut(analysis_df['TOTAL_PRIOR_CAREER_YEARS'], bins=bins, labels=labels, right=True)
    
    # Categorical 타입 변환
    if 'MAJOR_CATEGORY' in order_map:
        analysis_df['MAJOR_CATEGORY'] = pd.Categorical(analysis_df['MAJOR_CATEGORY'], categories=order_map['MAJOR_CATEGORY'], ordered=True)
    analysis_df['CAREER_BIN'] = pd.Categorical(analysis_df['CAREER_BIN'], categories=labels, ordered=True)

    return {"analysis_df": analysis_df, "order_map": order_map}

@st.cache_data
def prepare_proposal_11_data(
    filter_division='전체',
    filter_job_l1='전체',
    filter_position='전체',
    filter_gender='전체',
    filter_age_bin='전체',
    filter_career_bin='전체',
    filter_salary_bin='전체',
    filter_region='전체',
    filter_contract='전체'
):
    """
    제안 11: 근무 유연성 분석 (조직별 초과근무 분포)
    모든 차원 정보를 포함하여 분석 데이터를 생성합니다.
    """
    # 1. 필요한 모든 기본 데이터 로드
    base_data = load_all_base_data()
    emp_df = base_data["emp_df"]
    department_info_df = base_data["department_info_df"]
    job_info_df = base_data["job_info_df"]
    position_info_df = base_data["position_info_df"]
    career_info_df = base_data["career_info_df"]
    salary_contract_info_df = base_data["salary_contract_info_df"]
    region_info_df = base_data["region_info_df"]
    contract_info_df = base_data["contract_info_df"]
    department_df = base_data["department_df"]
    job_df = base_data["job_df"]
    position_df = base_data["position_df"]
    region_df = base_data["region_df"]
    daily_work_info_df = base_data["daily_work_info_df"]

    # 2. 글로벌 필터링을 위한 마스터 직원 테이블 생성
    emp_details = emp_df[['EMP_ID', 'GENDER', 'PERSONAL_ID', 'DURATION', 'IN_DATE', 'OUT_DATE']].copy()
    emp_details['GENDER'] = emp_details['GENDER'].map({'M': '남성', 'F': '여성'})
    emp_details['AGE'] = emp_details['PERSONAL_ID'].apply(calculate_age)
    emp_details['TENURE_YEARS'] = emp_details['DURATION'] / 365.25
    
    first_dept = department_info_df.sort_values('DEP_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_job = job_info_df.sort_values('JOB_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_pos = position_info_df.sort_values('GRADE_START_DATE').groupby('EMP_ID').first().reset_index()
    last_contract = contract_info_df.sort_values('CONT_START_DATE').groupby('EMP_ID').last().reset_index()
    last_region = region_info_df.sort_values('REG_APP_START_DATE').groupby('EMP_ID').last().reset_index()
    last_salary = salary_contract_info_df.sort_values('SAL_START_DATE').groupby('EMP_ID').last().reset_index()
    prior_career_summary = (career_info_df.groupby('EMP_ID')['CAREER_DURATION'].sum() / 365.25).reset_index(name='TOTAL_PRIOR_CAREER_YEARS')

    dept_level_map = department_df.set_index('DEP_ID')['DEP_LEVEL'].to_dict()
    parent_map_dept = department_df.set_index('DEP_ID')['UP_DEP_ID'].to_dict()
    dept_name_map = department_df.set_index('DEP_ID')['DEP_NAME'].to_dict()
    job_df_indexed = job_df.set_index('JOB_ID')
    parent_map_job = job_df_indexed['UP_JOB_ID'].to_dict()
    job_name_map = job_df.set_index('JOB_ID')['JOB_NAME'].to_dict()

    first_dept['DIVISION_NAME'] = first_dept['DEP_ID'].apply(lambda x: find_division_name_for_dept(x, dept_level_map, parent_map_dept, dept_name_map))
    first_job['JOB_L1_NAME'] = first_job['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    first_pos = pd.merge(first_pos, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID')
    last_region = pd.merge(last_region, region_df[['REG_ID', 'REG_NAME', 'DOMESTIC_YN']], on='REG_ID', how='left')
    last_region['REGION_CATEGORY'] = '해외 현장'; last_region.loc[last_region['DOMESTIC_YN'] == 'Y', 'REGION_CATEGORY'] = '국내 현장'; last_region.loc[last_region['REG_NAME'] == '서울특별시', 'REGION_CATEGORY'] = '서울 본사'
    
    emp_details = pd.merge(emp_details, first_dept[['EMP_ID', 'DIVISION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_job[['EMP_ID', 'JOB_L1_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_pos[['EMP_ID', 'POSITION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_contract[['EMP_ID', 'CONT_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_region[['EMP_ID', 'REGION_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_salary[['EMP_ID', 'SAL_AMOUNT', 'PAY_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, prior_career_summary, on='EMP_ID', how='left')
    emp_details['TOTAL_PRIOR_CAREER_YEARS'] = emp_details['TOTAL_PRIOR_CAREER_YEARS'].fillna(0)
    emp_details['TOTAL_CAREER_YEARS'] = emp_details['TENURE_YEARS'] + emp_details['TOTAL_PRIOR_CAREER_YEARS']
    
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    emp_details['SALARY_BIN'] = pd.cut(emp_details['ANNUAL_SALARY'], bins=salary_bins, labels=salary_labels, right=False)

    # 3. 글로벌 필터 적용
    filtered_emps_df = emp_details.copy()
    if filter_division != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['DIVISION_NAME'] == filter_division]
    if filter_job_l1 != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['JOB_L1_NAME'] == filter_job_l1]
    if filter_position != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['POSITION_NAME'] == filter_position]
    if filter_gender != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['GENDER'] == filter_gender]
    if filter_age_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['AGE_BIN'] == filter_age_bin]
    if filter_career_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CAREER_BIN'] == filter_career_bin]
    if filter_salary_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['SALARY_BIN'] == filter_salary_bin]
    if filter_region != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['REGION_CATEGORY'] == filter_region]
    if filter_contract != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CONT_CATEGORY'] == filter_contract]
    
    filtered_emp_ids = filtered_emps_df['EMP_ID'].unique()
    if len(filtered_emp_ids) == 0:
        return {"analysis_df": pd.DataFrame(), "order_map": order_map}

    # 4. 필터링된 직원들의 일별 초과근무 데이터에 모든 시점별 속성 정보 부여
    daily_work_df = daily_work_info_df[daily_work_info_df['EMP_ID'].isin(filtered_emp_ids)].copy()
    
    # 정렬된 이력 테이블 준비
    dept_info_sorted = department_info_df.sort_values(['DEP_APP_START_DATE', 'EMP_ID'])
    job_info_sorted = job_info_df.sort_values(['JOB_APP_START_DATE', 'EMP_ID'])
    pos_info_sorted = position_info_df.sort_values(['GRADE_START_DATE', 'EMP_ID'])

    analysis_df = daily_work_df.sort_values('DATE')
    
    # 시점별 부서, 직무, 직위 정보 병합
    analysis_df = pd.merge_asof(analysis_df, dept_info_sorted, left_on='DATE', right_on='DEP_APP_START_DATE', by='EMP_ID', direction='backward')
    analysis_df = pd.merge_asof(analysis_df, job_info_sorted, left_on='DATE', right_on='JOB_APP_START_DATE', by='EMP_ID', direction='backward')
    analysis_df = pd.merge_asof(analysis_df, pos_info_sorted, left_on='DATE', right_on='GRADE_START_DATE', by='EMP_ID', direction='backward')

    # 이름(Label) 정보 추가
    parent_info = analysis_df['DEP_ID'].apply(lambda x: find_parents(x, dept_level_map, parent_map_dept, dept_name_map))
    analysis_df = pd.concat([analysis_df, parent_info], axis=1)
    analysis_df['JOB_L1_NAME'] = analysis_df['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    analysis_df['JOB_L2_NAME'] = analysis_df['JOB_ID'].apply(lambda x: job_name_map.get(get_level2_ancestor(x, job_df_indexed, parent_map_job)))
    analysis_df = pd.merge(analysis_df, position_df[['POSITION_ID', 'POSITION_NAME']], on='POSITION_ID', how='left')
    
    # 나머지 정적/계산된 필터 속성 정보 병합 (filtered_emps_df에서 가져옴)
    attrs_to_merge = ['EMP_ID', 'GENDER', 'AGE_BIN', 'CAREER_BIN', 'SALARY_BIN', 'REGION_CATEGORY', 'CONT_CATEGORY']
    analysis_df = pd.merge(analysis_df, filtered_emps_df[attrs_to_merge], on='EMP_ID', how='left')

    # 최종 정리
    mask = analysis_df['OFFICE_NAME'].isnull()
    analysis_df.loc[mask, 'OFFICE_NAME'] = analysis_df.loc[mask, 'DIVISION_NAME'] + ' (직속)'
    
    analysis_df = analysis_df.dropna(subset=['DIVISION_NAME', 'OFFICE_NAME', 'JOB_L1_NAME', 'POSITION_NAME'])

    return {"analysis_df": analysis_df, "order_map": order_map}

@st.cache_data
def prepare_proposal_12_data(
    filter_division='전체',
    filter_job_l1='전체',
    filter_position='전체',
    filter_gender='전체',
    filter_age_bin='전체',
    filter_career_bin='전체',
    filter_salary_bin='전체',
    filter_region='전체',
    filter_contract='전체'
):
    """
    제안 12: 조직별/직위별 출근 문화 분석
    글로벌 필터를 적용하여 분석 대상을 선정한 뒤, 출근 시간 분포 분석 데이터를 생성합니다.
    """
    # 1. 필요한 모든 기본 데이터 로드
    base_data = load_all_base_data()
    emp_df = base_data["emp_df"]
    department_info_df = base_data["department_info_df"]
    job_info_df = base_data["job_info_df"]
    position_info_df = base_data["position_info_df"]
    career_info_df = base_data["career_info_df"]
    salary_contract_info_df = base_data["salary_contract_info_df"]
    region_info_df = base_data["region_info_df"]
    contract_info_df = base_data["contract_info_df"]
    department_df = base_data["department_df"]
    job_df = base_data["job_df"]
    position_df = base_data["position_df"]
    region_df = base_data["region_df"]
    detailed_work_info_df = base_data["detailed_work_info_df"]
    work_info_df = base_data["work_info_df"]

    # 2. 글로벌 필터링을 위한 마스터 직원 테이블 생성
    emp_details = emp_df[['EMP_ID', 'GENDER', 'PERSONAL_ID', 'DURATION', 'IN_DATE', 'OUT_DATE']].copy()
    emp_details['GENDER'] = emp_details['GENDER'].map({'M': '남성', 'F': '여성'})
    emp_details['AGE'] = emp_details['PERSONAL_ID'].apply(calculate_age)
    emp_details['TENURE_YEARS'] = emp_details['DURATION'] / 365.25
    
    first_dept = department_info_df.sort_values('DEP_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_job = job_info_df.sort_values('JOB_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_pos = position_info_df.sort_values('GRADE_START_DATE').groupby('EMP_ID').first().reset_index()
    last_contract = contract_info_df.sort_values('CONT_START_DATE').groupby('EMP_ID').last().reset_index()
    last_region = region_info_df.sort_values('REG_APP_START_DATE').groupby('EMP_ID').last().reset_index()
    last_salary = salary_contract_info_df.sort_values('SAL_START_DATE').groupby('EMP_ID').last().reset_index()
    prior_career_summary = (career_info_df.groupby('EMP_ID')['CAREER_DURATION'].sum() / 365.25).reset_index(name='TOTAL_PRIOR_CAREER_YEARS')

    dept_level_map = department_df.set_index('DEP_ID')['DEP_LEVEL'].to_dict()
    parent_map_dept = department_df.set_index('DEP_ID')['UP_DEP_ID'].to_dict()
    dept_name_map = department_df.set_index('DEP_ID')['DEP_NAME'].to_dict()
    job_df_indexed = job_df.set_index('JOB_ID')
    parent_map_job = job_df_indexed['UP_JOB_ID'].to_dict()
    job_name_map = job_df.set_index('JOB_ID')['JOB_NAME'].to_dict()

    first_dept['DIVISION_NAME'] = first_dept['DEP_ID'].apply(lambda x: find_division_name_for_dept(x, dept_level_map, parent_map_dept, dept_name_map))
    first_job['JOB_L1_NAME'] = first_job['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    first_pos = pd.merge(first_pos, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID')
    last_region = pd.merge(last_region, region_df[['REG_ID', 'REG_NAME', 'DOMESTIC_YN']], on='REG_ID', how='left')
    last_region['REGION_CATEGORY'] = '해외 현장'; last_region.loc[last_region['DOMESTIC_YN'] == 'Y', 'REGION_CATEGORY'] = '국내 현장'; last_region.loc[last_region['REG_NAME'] == '서울특별시', 'REGION_CATEGORY'] = '서울 본사'
    
    emp_details = pd.merge(emp_details, first_dept[['EMP_ID', 'DIVISION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_job[['EMP_ID', 'JOB_L1_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_pos[['EMP_ID', 'POSITION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_contract[['EMP_ID', 'CONT_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_region[['EMP_ID', 'REGION_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_salary[['EMP_ID', 'SAL_AMOUNT', 'PAY_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, prior_career_summary, on='EMP_ID', how='left')
    emp_details['TOTAL_PRIOR_CAREER_YEARS'] = emp_details['TOTAL_PRIOR_CAREER_YEARS'].fillna(0)
    emp_details['TOTAL_CAREER_YEARS'] = emp_details['TENURE_YEARS'] + emp_details['TOTAL_PRIOR_CAREER_YEARS']
    
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    emp_details['SALARY_BIN'] = pd.cut(emp_details['ANNUAL_SALARY'], bins=salary_bins, labels=salary_labels, right=False)

    # 3. 글로벌 필터 적용
    filtered_emps_df = emp_details.copy()
    if filter_division != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['DIVISION_NAME'] == filter_division]
    if filter_job_l1 != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['JOB_L1_NAME'] == filter_job_l1]
    if filter_position != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['POSITION_NAME'] == filter_position]
    if filter_gender != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['GENDER'] == filter_gender]
    if filter_age_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['AGE_BIN'] == filter_age_bin]
    if filter_career_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CAREER_BIN'] == filter_career_bin]
    if filter_salary_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['SALARY_BIN'] == filter_salary_bin]
    if filter_region != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['REGION_CATEGORY'] == filter_region]
    if filter_contract != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CONT_CATEGORY'] == filter_contract]
    
    filtered_emp_ids = filtered_emps_df['EMP_ID'].unique()
    if len(filtered_emp_ids) == 0:
        return {"analysis_df": pd.DataFrame(), "order_map": order_map}

    # 4. 필터링된 직원들의 일별 출근 데이터 준비 (샘플링 포함)
    normal_work_emp_ids = work_info_df[work_info_df['WORK_SYS_ID'] == 'WS001']['EMP_ID'].unique()
    target_emp_ids = np.intersect1d(normal_work_emp_ids, filtered_emp_ids)
    
    if len(target_emp_ids) > 0:
        num_to_sample = int(len(target_emp_ids) * 0.3) if len(target_emp_ids) > 10 else len(target_emp_ids)
        np.random.seed(42)
        sampled_emp_ids = np.random.choice(target_emp_ids, size=num_to_sample, replace=False)
    else:
        return {"analysis_df": pd.DataFrame(), "order_map": order_map}

    work_records = detailed_work_info_df[
        (detailed_work_info_df['EMP_ID'].isin(sampled_emp_ids)) &
        (~detailed_work_info_df['WORK_ETC'].isin(['휴가', '주말 휴무', '비번', '휴무'])) &
        (detailed_work_info_df['DATE_START_TIME'] != '-')
    ].copy()
    work_records['DATE'] = pd.to_datetime(work_records['DATE'])
    
    # 5. 시점별 속성 정보 부여
    dept_info_sorted = department_info_df.sort_values('DEP_APP_START_DATE')
    job_info_sorted = job_info_df.sort_values('JOB_APP_START_DATE')
    pos_info_sorted = position_info_df.sort_values('GRADE_START_DATE')

    analysis_df = work_records.sort_values('DATE')
    analysis_df = pd.merge_asof(analysis_df, dept_info_sorted, left_on='DATE', right_on='DEP_APP_START_DATE', by='EMP_ID', direction='backward')
    analysis_df = pd.merge_asof(analysis_df, job_info_sorted, left_on='DATE', right_on='JOB_APP_START_DATE', by='EMP_ID', direction='backward')
    analysis_df = pd.merge_asof(analysis_df, pos_info_sorted, left_on='DATE', right_on='GRADE_START_DATE', by='EMP_ID', direction='backward')

    parent_info = analysis_df['DEP_ID'].apply(lambda x: find_parents(x, dept_level_map, parent_map_dept, dept_name_map))
    analysis_df = pd.concat([analysis_df, parent_info], axis=1)
    analysis_df['JOB_L1_NAME'] = analysis_df['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    analysis_df['JOB_L2_NAME'] = analysis_df['JOB_ID'].apply(lambda x: job_name_map.get(get_level2_ancestor(x, job_df_indexed, parent_map_job)))
    analysis_df = pd.merge(analysis_df, position_df[['POSITION_ID', 'POSITION_NAME']], on='POSITION_ID', how='left')

    attrs_to_merge = ['EMP_ID', 'GENDER', 'AGE_BIN', 'CAREER_BIN', 'SALARY_BIN', 'REGION_CATEGORY', 'CONT_CATEGORY']
    analysis_df = pd.merge(analysis_df, filtered_emps_df[attrs_to_merge], on='EMP_ID', how='left')

    analysis_df = analysis_df.dropna(subset=['DIVISION_NAME', 'OFFICE_NAME', 'POSITION_NAME', 'JOB_L1_NAME', 'JOB_L2_NAME'])

    # 6. 출근 시간(float) 계산
    analysis_df['START_HOUR'] = pd.to_datetime(analysis_df['DATE_START_TIME'], format='%H:%M', errors='coerce').dt.hour + \
                                pd.to_datetime(analysis_df['DATE_START_TIME'], format='%H:%M', errors='coerce').dt.minute / 60
    analysis_df = analysis_df.dropna(subset=['START_HOUR'])

    return {"analysis_df": analysis_df, "order_map": order_map}

@st.cache_data
def prepare_proposal_13_data(
    filter_division='전체',
    filter_job_l1='전체',
    filter_position='전체',
    filter_gender='전체',
    filter_age_bin='전체',
    filter_career_bin='전체',
    filter_salary_bin='전체',
    filter_region='전체',
    filter_contract='전체'
):
    """
    제안 13: 조직 워라밸 변화 추이 (월 평균 1인당 초과근무 시간)
    모든 차원 정보를 포함하여 분석 데이터를 생성합니다.
    """
    # 1. 필요한 모든 기본 데이터 로드
    base_data = load_all_base_data()
    emp_df = base_data["emp_df"]
    department_info_df = base_data["department_info_df"]
    job_info_df = base_data["job_info_df"]
    position_info_df = base_data["position_info_df"]
    career_info_df = base_data["career_info_df"]
    salary_contract_info_df = base_data["salary_contract_info_df"]
    region_info_df = base_data["region_info_df"]
    contract_info_df = base_data["contract_info_df"]
    department_df = base_data["department_df"]
    job_df = base_data["job_df"]
    position_df = base_data["position_df"]
    region_df = base_data["region_df"]
    daily_work_info_df = base_data["daily_work_info_df"]

    # 2. 글로벌 필터링을 위한 마스터 직원 테이블 생성
    emp_details = emp_df[['EMP_ID', 'GENDER', 'PERSONAL_ID', 'DURATION', 'IN_DATE', 'OUT_DATE']].copy()
    emp_details['GENDER'] = emp_details['GENDER'].map({'M': '남성', 'F': '여성'})
    emp_details['AGE'] = emp_details['PERSONAL_ID'].apply(calculate_age)
    emp_details['TENURE_YEARS'] = emp_details['DURATION'] / 365.25
    
    first_dept = department_info_df.sort_values('DEP_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_job = job_info_df.sort_values('JOB_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_pos = position_info_df.sort_values('GRADE_START_DATE').groupby('EMP_ID').first().reset_index()
    last_contract = contract_info_df.sort_values('CONT_START_DATE').groupby('EMP_ID').last().reset_index()
    last_region = region_info_df.sort_values('REG_APP_START_DATE').groupby('EMP_ID').last().reset_index()
    last_salary = salary_contract_info_df.sort_values('SAL_START_DATE').groupby('EMP_ID').last().reset_index()
    prior_career_summary = (career_info_df.groupby('EMP_ID')['CAREER_DURATION'].sum() / 365.25).reset_index(name='TOTAL_PRIOR_CAREER_YEARS')

    dept_level_map = department_df.set_index('DEP_ID')['DEP_LEVEL'].to_dict()
    parent_map_dept = department_df.set_index('DEP_ID')['UP_DEP_ID'].to_dict()
    dept_name_map = department_df.set_index('DEP_ID')['DEP_NAME'].to_dict()
    job_df_indexed = job_df.set_index('JOB_ID')
    parent_map_job = job_df_indexed['UP_JOB_ID'].to_dict()
    job_name_map = job_df.set_index('JOB_ID')['JOB_NAME'].to_dict()

    first_dept['DIVISION_NAME'] = first_dept['DEP_ID'].apply(lambda x: find_division_name_for_dept(x, dept_level_map, parent_map_dept, dept_name_map))
    first_job['JOB_L1_NAME'] = first_job['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    first_pos = pd.merge(first_pos, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID')
    last_region = pd.merge(last_region, region_df[['REG_ID', 'REG_NAME', 'DOMESTIC_YN']], on='REG_ID', how='left')
    last_region['REGION_CATEGORY'] = '해외 현장'; last_region.loc[last_region['DOMESTIC_YN'] == 'Y', 'REGION_CATEGORY'] = '국내 현장'; last_region.loc[last_region['REG_NAME'] == '서울특별시', 'REGION_CATEGORY'] = '서울 본사'
    
    emp_details = pd.merge(emp_details, first_dept[['EMP_ID', 'DIVISION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_job[['EMP_ID', 'JOB_L1_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_pos[['EMP_ID', 'POSITION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_contract[['EMP_ID', 'CONT_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_region[['EMP_ID', 'REGION_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_salary[['EMP_ID', 'SAL_AMOUNT', 'PAY_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, prior_career_summary, on='EMP_ID', how='left')
    emp_details['TOTAL_PRIOR_CAREER_YEARS'] = emp_details['TOTAL_PRIOR_CAREER_YEARS'].fillna(0)
    emp_details['TOTAL_CAREER_YEARS'] = emp_details['TENURE_YEARS'] + emp_details['TOTAL_PRIOR_CAREER_YEARS']
    
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    emp_details['SALARY_BIN'] = pd.cut(emp_details['ANNUAL_SALARY'], bins=salary_bins, labels=salary_labels, right=False)

    # 3. 글로벌 필터 적용
    filtered_emps_df = emp_details.copy()
    if filter_division != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['DIVISION_NAME'] == filter_division]
    if filter_job_l1 != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['JOB_L1_NAME'] == filter_job_l1]
    if filter_position != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['POSITION_NAME'] == filter_position]
    if filter_gender != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['GENDER'] == filter_gender]
    if filter_age_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['AGE_BIN'] == filter_age_bin]
    if filter_career_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CAREER_BIN'] == filter_career_bin]
    if filter_salary_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['SALARY_BIN'] == filter_salary_bin]
    if filter_region != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['REGION_CATEGORY'] == filter_region]
    if filter_contract != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CONT_CATEGORY'] == filter_contract]
    
    filtered_emp_ids = filtered_emps_df['EMP_ID'].unique()
    if len(filtered_emp_ids) == 0:
        return {"analysis_df": pd.DataFrame(), "order_map": order_map}

    # 4. 필터링된 직원들의 일별 초과근무 데이터에 모든 시점별 속성 정보 부여
    daily_work_df = daily_work_info_df[daily_work_info_df['EMP_ID'].isin(filtered_emp_ids)].copy()
    daily_work_df['DATE'] = pd.to_datetime(daily_work_df['DATE'])
    
    dept_info_sorted = department_info_df.sort_values('DEP_APP_START_DATE')
    job_info_sorted = job_info_df.sort_values('JOB_APP_START_DATE')
    pos_info_with_name = pd.merge(position_info_df, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID')
    pos_info_sorted = pos_info_with_name.sort_values('GRADE_START_DATE')

    analysis_df = daily_work_df.sort_values('DATE')
    analysis_df = pd.merge_asof(analysis_df, dept_info_sorted, left_on='DATE', right_on='DEP_APP_START_DATE', by='EMP_ID', direction='backward')
    analysis_df = pd.merge_asof(analysis_df, job_info_sorted, left_on='DATE', right_on='JOB_APP_START_DATE', by='EMP_ID', direction='backward')
    analysis_df = pd.merge_asof(analysis_df, pos_info_sorted, left_on='DATE', right_on='GRADE_START_DATE', by='EMP_ID', direction='backward')

    parent_info = analysis_df['DEP_ID'].apply(lambda x: find_parents(x, dept_level_map, parent_map_dept, dept_name_map))
    analysis_df = pd.concat([analysis_df, parent_info], axis=1)
    analysis_df['JOB_L1_NAME'] = analysis_df['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    analysis_df['JOB_L2_NAME'] = analysis_df['JOB_ID'].apply(lambda x: job_name_map.get(get_level2_ancestor(x, job_df_indexed, parent_map_job)))
    
    attrs_to_merge = ['EMP_ID', 'GENDER', 'AGE_BIN', 'CAREER_BIN', 'SALARY_BIN', 'REGION_CATEGORY', 'CONT_CATEGORY']
    emp_attrs = filtered_emps_df[attrs_to_merge].drop_duplicates(subset=['EMP_ID'])
    analysis_df = pd.merge(analysis_df, emp_attrs, on='EMP_ID', how='left')

    analysis_df = analysis_df.dropna(subset=['DIVISION_NAME', 'OFFICE_NAME', 'JOB_L1_NAME', 'JOB_L2_NAME', 'POSITION_NAME', 'GRADE_ID'])
    
    return {"analysis_df": analysis_df, "order_map": order_map}

@st.cache_data
def prepare_proposal_14_data(
    filter_division='전체',
    filter_job_l1='전체',
    filter_position='전체',
    filter_gender='전체',
    filter_age_bin='전체',
    filter_career_bin='전체',
    filter_salary_bin='전체',
    filter_region='전체',
    filter_contract='전체'
):
    """
    제안 14: 조직별/직위별 지각률(%) 분석
    글로벌 필터를 적용하여 분석 대상을 선정한 뒤, 지각률 분석 데이터를 생성합니다.
    """
    # 1. 필요한 모든 기본 데이터 로드
    base_data = load_all_base_data()
    emp_df = base_data["emp_df"]
    department_info_df = base_data["department_info_df"]
    job_info_df = base_data["job_info_df"]
    position_info_df = base_data["position_info_df"]
    career_info_df = base_data["career_info_df"]
    salary_contract_info_df = base_data["salary_contract_info_df"]
    region_info_df = base_data["region_info_df"]
    contract_info_df = base_data["contract_info_df"]
    department_df = base_data["department_df"]
    job_df = base_data["job_df"]
    position_df = base_data["position_df"]
    region_df = base_data["region_df"]
    detailed_work_info_df = base_data["detailed_work_info_df"]
    work_info_df = base_data["work_info_df"]

    # 2. 글로벌 필터링을 위한 마스터 직원 테이블 생성
    emp_details = emp_df[['EMP_ID', 'GENDER', 'PERSONAL_ID', 'DURATION', 'IN_DATE', 'OUT_DATE']].copy()
    emp_details['GENDER'] = emp_details['GENDER'].map({'M': '남성', 'F': '여성'})
    emp_details['AGE'] = emp_details['PERSONAL_ID'].apply(calculate_age)
    emp_details['TENURE_YEARS'] = emp_details['DURATION'] / 365.25

    first_dept = department_info_df.sort_values('DEP_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_job = job_info_df.sort_values('JOB_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_pos = position_info_df.sort_values('GRADE_START_DATE').groupby('EMP_ID').first().reset_index()
    last_contract = contract_info_df.sort_values('CONT_START_DATE').groupby('EMP_ID').last().reset_index()
    last_region = region_info_df.sort_values('REG_APP_START_DATE').groupby('EMP_ID').last().reset_index()
    last_salary = salary_contract_info_df.sort_values('SAL_START_DATE').groupby('EMP_ID').last().reset_index()
    prior_career_summary = (career_info_df.groupby('EMP_ID')['CAREER_DURATION'].sum() / 365.25).reset_index(name='TOTAL_PRIOR_CAREER_YEARS')

    dept_level_map = department_df.set_index('DEP_ID')['DEP_LEVEL'].to_dict()
    parent_map_dept = department_df.set_index('DEP_ID')['UP_DEP_ID'].to_dict()
    dept_name_map = department_df.set_index('DEP_ID')['DEP_NAME'].to_dict()
    job_df_indexed = job_df.set_index('JOB_ID')
    parent_map_job = job_df_indexed['UP_JOB_ID'].to_dict()
    job_name_map = job_df.set_index('JOB_ID')['JOB_NAME'].to_dict()

    first_dept['DIVISION_NAME'] = first_dept['DEP_ID'].apply(lambda x: find_division_name_for_dept(x, dept_level_map, parent_map_dept, dept_name_map))
    first_job['JOB_L1_NAME'] = first_job['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    first_pos = pd.merge(first_pos, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID')
    last_region = pd.merge(last_region, region_df[['REG_ID', 'REG_NAME', 'DOMESTIC_YN']], on='REG_ID', how='left')
    last_region['REGION_CATEGORY'] = '해외 현장'; last_region.loc[last_region['DOMESTIC_YN'] == 'Y', 'REGION_CATEGORY'] = '국내 현장'; last_region.loc[last_region['REG_NAME'] == '서울특별시', 'REGION_CATEGORY'] = '서울 본사'

    emp_details = pd.merge(emp_details, first_dept[['EMP_ID', 'DIVISION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_job[['EMP_ID', 'JOB_L1_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_pos[['EMP_ID', 'POSITION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_contract[['EMP_ID', 'CONT_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_region[['EMP_ID', 'REGION_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_salary[['EMP_ID', 'SAL_AMOUNT', 'PAY_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, prior_career_summary, on='EMP_ID', how='left')
    emp_details['TOTAL_PRIOR_CAREER_YEARS'] = emp_details['TOTAL_PRIOR_CAREER_YEARS'].fillna(0)
    emp_details['TOTAL_CAREER_YEARS'] = emp_details['TENURE_YEARS'] + emp_details['TOTAL_PRIOR_CAREER_YEARS']

    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    emp_details['SALARY_BIN'] = pd.cut(emp_details['ANNUAL_SALARY'], bins=salary_bins, labels=salary_labels, right=False)

    # 3. 글로벌 필터 적용
    filtered_emps_df = emp_details.copy()
    if filter_division != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['DIVISION_NAME'] == filter_division]
    if filter_job_l1 != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['JOB_L1_NAME'] == filter_job_l1]
    if filter_position != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['POSITION_NAME'] == filter_position]
    if filter_gender != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['GENDER'] == filter_gender]
    if filter_age_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['AGE_BIN'] == filter_age_bin]
    if filter_career_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CAREER_BIN'] == filter_career_bin]
    if filter_salary_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['SALARY_BIN'] == filter_salary_bin]
    if filter_region != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['REGION_CATEGORY'] == filter_region]
    if filter_contract != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CONT_CATEGORY'] == filter_contract]
    
    filtered_emp_ids = filtered_emps_df['EMP_ID'].unique()
    if len(filtered_emp_ids) == 0:
        return {"analysis_df": pd.DataFrame(), "order_map": order_map}

    # 4. 필터링된 직원들의 일별 지각 데이터 준비
    work_records = detailed_work_info_df.copy()
    work_records = work_records[~work_records['WORK_ETC'].isin(['휴가', '주말 휴무', '비번', '휴무'])]
    work_records = work_records[work_records['DATE_START_TIME'] != '-']
    normal_work_emp_ids = work_info_df[work_info_df['WORK_SYS_ID'] == 'WS001']['EMP_ID'].unique()
    
    target_emp_ids = np.intersect1d(normal_work_emp_ids, filtered_emp_ids)
    work_records = work_records[work_records['EMP_ID'].isin(target_emp_ids)].copy()

    if work_records.empty:
        return {"analysis_df": pd.DataFrame(), "order_map": order_map}
    
    work_records['DATE'] = pd.to_datetime(work_records['DATE'])
    
    # 5. 시점별 속성 정보 부여
    pos_info_sorted = position_info_df.sort_values('GRADE_START_DATE')
    job_info_sorted = job_info_df.sort_values('JOB_APP_START_DATE')
    dept_info_sorted = department_info_df.sort_values('DEP_APP_START_DATE')
    analysis_df = work_records.sort_values('DATE')
    
    analysis_df = pd.merge_asof(analysis_df, pos_info_sorted, left_on='DATE', right_on='GRADE_START_DATE', by='EMP_ID', direction='backward')
    analysis_df = pd.merge_asof(analysis_df, job_info_sorted, left_on='DATE', right_on='JOB_APP_START_DATE', by='EMP_ID', direction='backward')
    analysis_df = pd.merge_asof(analysis_df, dept_info_sorted, left_on='DATE', right_on='DEP_APP_START_DATE', by='EMP_ID', direction='backward')
    
    analysis_df = pd.merge(analysis_df, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID', how='left')
    analysis_df['JOB_L1_NAME'] = analysis_df['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    analysis_df['JOB_L2_NAME'] = analysis_df['JOB_ID'].apply(lambda x: job_name_map.get(get_level2_ancestor(x, job_df_indexed, parent_map_job)))
    parent_info = analysis_df['DEP_ID'].apply(lambda x: find_parents(x, dept_level_map, parent_map_dept, dept_name_map))
    analysis_df = pd.concat([analysis_df, parent_info], axis=1)

    attrs_to_merge = ['EMP_ID', 'GENDER', 'AGE_BIN', 'CAREER_BIN', 'SALARY_BIN', 'REGION_CATEGORY', 'CONT_CATEGORY']
    emp_attrs = filtered_emps_df[attrs_to_merge].drop_duplicates(subset=['EMP_ID'])
    analysis_df = pd.merge(analysis_df, emp_attrs, on='EMP_ID', how='left')
    
    analysis_df = analysis_df.dropna(subset=['JOB_L1_NAME', 'JOB_L2_NAME', 'POSITION_NAME', 'DIVISION_NAME', 'OFFICE_NAME'])
    
    # 6. '지각' 여부 판단
    analysis_df['START_TIME_OBJ'] = pd.to_datetime(analysis_df['DATE_START_TIME'], format='%H:%M', errors='coerce').dt.time
    gso_mask = analysis_df['OFFICE_NAME'] == 'Global Sales Office'
    analysis_df['IS_LATE'] = False
    
    not_na_mask = analysis_df['START_TIME_OBJ'].notna()
    analysis_df.loc[gso_mask & not_na_mask, 'IS_LATE'] = analysis_df.loc[gso_mask & not_na_mask, 'START_TIME_OBJ'] > datetime.time(11, 0)
    analysis_df.loc[~gso_mask & not_na_mask, 'IS_LATE'] = analysis_df.loc[~gso_mask & not_na_mask, 'START_TIME_OBJ'] > datetime.time(10, 0)

    # 7. 분석에서 특정 연령대 제외
    age_filter = ['20세 미만', '50세 이상']
    analysis_df = analysis_df[~analysis_df['AGE_BIN'].isin(age_filter)]

    return {"analysis_df": analysis_df, "order_map": order_map}

@st.cache_data
def prepare_proposal_15_data(
    filter_division='전체',
    filter_job_l1='전체',
    filter_position='전체',
    filter_gender='전체',
    filter_age_bin='전체',
    filter_career_bin='전체',
    filter_salary_bin='전체',
    filter_region='전체',
    filter_contract='전체'
):
    """
    제안 15: 부서 변경 전후 초과근무 패턴 분석
    글로벌 필터를 적용하여 분석 대상을 선정한 뒤, 부서 변경 전후 초과근무 패턴 분석 데이터를 생성합니다.
    """
    # 1. 필요한 모든 기본 데이터 로드
    base_data = load_all_base_data()
    emp_df = base_data["emp_df"]
    department_info_df = base_data["department_info_df"]
    job_info_df = base_data["job_info_df"]
    position_info_df = base_data["position_info_df"]
    career_info_df = base_data["career_info_df"]
    salary_contract_info_df = base_data["salary_contract_info_df"]
    region_info_df = base_data["region_info_df"]
    contract_info_df = base_data["contract_info_df"]
    department_df = base_data["department_df"]
    job_df = base_data["job_df"]
    position_df = base_data["position_df"]
    region_df = base_data["region_df"]
    daily_work_info_df = base_data["daily_work_info_df"]

    # 2. 글로벌 필터링을 위한 마스터 직원 테이블 생성
    emp_details = emp_df[['EMP_ID', 'GENDER', 'PERSONAL_ID', 'DURATION', 'IN_DATE', 'OUT_DATE']].copy()
    emp_details['GENDER'] = emp_details['GENDER'].map({'M': '남성', 'F': '여성'})
    emp_details['AGE'] = emp_details['PERSONAL_ID'].apply(calculate_age)
    emp_details['TENURE_YEARS'] = emp_details['DURATION'] / 365.25
    
    first_dept = department_info_df.sort_values('DEP_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_job = job_info_df.sort_values('JOB_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_pos = position_info_df.sort_values('GRADE_START_DATE').groupby('EMP_ID').first().reset_index()
    last_contract = contract_info_df.sort_values('CONT_START_DATE').groupby('EMP_ID').last().reset_index()
    last_region = region_info_df.sort_values('REG_APP_START_DATE').groupby('EMP_ID').last().reset_index()
    last_salary = salary_contract_info_df.sort_values('SAL_START_DATE').groupby('EMP_ID').last().reset_index()
    prior_career_summary = (career_info_df.groupby('EMP_ID')['CAREER_DURATION'].sum() / 365.25).reset_index(name='TOTAL_PRIOR_CAREER_YEARS')

    dept_level_map = department_df.set_index('DEP_ID')['DEP_LEVEL'].to_dict()
    parent_map_dept = department_df.set_index('DEP_ID')['UP_DEP_ID'].to_dict()
    dept_name_map = department_df.set_index('DEP_ID')['DEP_NAME'].to_dict()
    job_df_indexed = job_df.set_index('JOB_ID')
    parent_map_job = job_df_indexed['UP_JOB_ID'].to_dict()
    job_name_map = job_df.set_index('JOB_ID')['JOB_NAME'].to_dict()

    first_dept['DIVISION_NAME'] = first_dept['DEP_ID'].apply(lambda x: find_division_name_for_dept(x, dept_level_map, parent_map_dept, dept_name_map))
    first_job['JOB_L1_NAME'] = first_job['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    first_pos = pd.merge(first_pos, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID')
    last_region = pd.merge(last_region, region_df[['REG_ID', 'REG_NAME', 'DOMESTIC_YN']], on='REG_ID', how='left')
    last_region['REGION_CATEGORY'] = '해외 현장'; last_region.loc[last_region['DOMESTIC_YN'] == 'Y', 'REGION_CATEGORY'] = '국내 현장'; last_region.loc[last_region['REG_NAME'] == '서울특별시', 'REGION_CATEGORY'] = '서울 본사'

    emp_details = pd.merge(emp_details, first_dept[['EMP_ID', 'DIVISION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_job[['EMP_ID', 'JOB_L1_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_pos[['EMP_ID', 'POSITION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_contract[['EMP_ID', 'CONT_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_region[['EMP_ID', 'REGION_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_salary[['EMP_ID', 'SAL_AMOUNT', 'PAY_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, prior_career_summary, on='EMP_ID', how='left')
    emp_details['TOTAL_PRIOR_CAREER_YEARS'] = emp_details['TOTAL_PRIOR_CAREER_YEARS'].fillna(0)
    emp_details['TOTAL_CAREER_YEARS'] = emp_details['TENURE_YEARS'] + emp_details['TOTAL_PRIOR_CAREER_YEARS']
    
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    emp_details['SALARY_BIN'] = pd.cut(emp_details['ANNUAL_SALARY'], bins=salary_bins, labels=salary_labels, right=False)

    # 3. 글로벌 필터 적용
    filtered_emps_df = emp_details.copy()
    if filter_division != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['DIVISION_NAME'] == filter_division]
    if filter_job_l1 != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['JOB_L1_NAME'] == filter_job_l1]
    if filter_position != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['POSITION_NAME'] == filter_position]
    if filter_gender != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['GENDER'] == filter_gender]
    if filter_age_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['AGE_BIN'] == filter_age_bin]
    if filter_career_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CAREER_BIN'] == filter_career_bin]
    if filter_salary_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['SALARY_BIN'] == filter_salary_bin]
    if filter_region != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['REGION_CATEGORY'] == filter_region]
    if filter_contract != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CONT_CATEGORY'] == filter_contract]
    
    filtered_emp_ids = filtered_emps_df['EMP_ID'].unique()
    if len(filtered_emp_ids) == 0:
        return {"analysis_df": pd.DataFrame(), "order_map": order_map}

    # 4. 필터링된 직원들의 부서 이동 이벤트 식별
    dept_changes = department_info_df[department_info_df['EMP_ID'].isin(filtered_emp_ids)].sort_values(['EMP_ID', 'DEP_APP_START_DATE'])
    dept_changes['PREV_DEP_ID'] = dept_changes.groupby('EMP_ID')['DEP_ID'].shift(1)
    dept_changes = dept_changes[dept_changes['PREV_DEP_ID'].notna() & (dept_changes['DEP_ID'] != dept_changes['PREV_DEP_ID'])].copy()
    dept_changes = dept_changes.rename(columns={'DEP_APP_START_DATE': 'CHANGE_DATE'})

    if dept_changes.empty:
        return {"analysis_df": pd.DataFrame(), "order_map": order_map}

    # 5. 각 이동 이벤트별 전/후 초과근무 계산
    daily_work_filtered_df = daily_work_info_df[daily_work_info_df['EMP_ID'].isin(dept_changes['EMP_ID'].unique())].copy()
    
    pattern_records = []
    for _, row in dept_changes.iterrows():
        emp_id, change_date = row['EMP_ID'], row['CHANGE_DATE']
        before_start, after_end = change_date - pd.DateOffset(months=3), change_date + pd.DateOffset(months=3)
        emp_work_df = daily_work_filtered_df[daily_work_filtered_df['EMP_ID'] == emp_id]
        
        ot_before = emp_work_df[emp_work_df['DATE'].between(before_start, change_date - pd.DateOffset(days=1))]['OVERTIME_MINUTES'].mean()
        ot_after = emp_work_df[emp_work_df['DATE'].between(change_date, after_end)]['OVERTIME_MINUTES'].mean()
        
        if pd.notna(ot_before) and pd.notna(ot_after):
            pattern_records.append({'EMP_ID': emp_id, 'CHANGE_DATE': change_date, 'NEW_DEP_ID': row['DEP_ID'], 'OT_BEFORE': ot_before, 'OT_AFTER': ot_after})
    
    analysis_df = pd.DataFrame(pattern_records)
    if analysis_df.empty:
        return {"analysis_df": pd.DataFrame(), "order_map": order_map}

    # 6. 부서 평균(Baseline) 계산 (전체 직원 기준)
    daily_work_with_dept = pd.merge_asof(daily_work_info_df.sort_values('DATE'), department_info_df.sort_values('DEP_APP_START_DATE'), left_on='DATE', right_on='DEP_APP_START_DATE', by='EMP_ID', direction='backward')
    parent_info_daily = daily_work_with_dept['DEP_ID'].apply(lambda x: find_parents(x, dept_level_map, parent_map_dept, dept_name_map))
    daily_work_with_dept = pd.concat([daily_work_with_dept, parent_info_daily], axis=1)
    daily_work_with_dept = daily_work_with_dept.dropna(subset=['DIVISION_NAME', 'OFFICE_NAME'])
    
    div_overall_avg = daily_work_with_dept.groupby('DIVISION_NAME', observed=False)['OVERTIME_MINUTES'].mean().reset_index().rename(columns={'OVERTIME_MINUTES': 'DEPT_AVG'})
    office_overall_avg = daily_work_with_dept.groupby(['DIVISION_NAME','OFFICE_NAME'], observed=False)['OVERTIME_MINUTES'].mean().reset_index().rename(columns={'OVERTIME_MINUTES': 'DEPT_AVG'})
    
    # 7. 최종 분석 데이터프레임 생성
    parent_info = analysis_df['NEW_DEP_ID'].apply(lambda x: find_parents(x, dept_level_map, parent_map_dept, dept_name_map))
    analysis_df = pd.concat([analysis_df, parent_info], axis=1)
    analysis_df = analysis_df.dropna(subset=['DIVISION_NAME', 'OFFICE_NAME'])

    # 부서 평균(DEPT_AVG)을 analysis_df에 병합
    analysis_df = pd.merge(analysis_df, div_overall_avg, on='DIVISION_NAME', how='left', suffixes=('', '_div'))
    analysis_df = pd.merge(analysis_df, office_overall_avg, on=['DIVISION_NAME', 'OFFICE_NAME'], how='left', suffixes=('', '_office'))
    
    # Office 레벨의 평균이 있으면 그것을 사용하고, 없으면 Division 레벨 평균 사용
    analysis_df['DEPT_AVG'] = analysis_df['DEPT_AVG_office'].fillna(analysis_df['DEPT_AVG'])
    analysis_df = analysis_df.drop(columns=['DEPT_AVG_div', 'DEPT_AVG_office'], errors='ignore')

    return {"analysis_df": analysis_df, "order_map": order_map}

@st.cache_data
def prepare_proposal_16_data(
    filter_division='전체',
    filter_job_l1='전체',
    filter_position='전체',
    filter_gender='전체',
    filter_age_bin='전체',
    filter_career_bin='전체',
    filter_salary_bin='전체',
    filter_region='전체',
    filter_contract='전체'
):
    """
    제안 16: 주말 근무 패턴 분석
    글로벌 필터를 적용하여 분석 대상을 선정한 뒤, 월 평균 주말 근무일수 분석 데이터를 생성합니다.
    """
    # 1. 모든 재직자의 최신 상태 정보가 담긴 스냅샷 데이터를 불러옵니다. (캐싱됨)
    snapshot_df = _get_current_employee_snapshot()

    # 2. 글로벌 필터 적용
    filtered_df = snapshot_df.copy()
    if filter_division != '전체':
        filtered_df = filtered_df[filtered_df['DIVISION_NAME'] == filter_division]
    if filter_job_l1 != '전체':
        filtered_df = filtered_df[filtered_df['JOB_L1_NAME'] == filter_job_l1]
    if filter_position != '전체':
        filtered_df = filtered_df[filtered_df['POSITION_NAME'] == filter_position]
    if filter_gender != '전체':
        filtered_df = filtered_df[filtered_df['GENDER'] == filter_gender]
    if filter_age_bin != '전체':
        filtered_df = filtered_df[filtered_df['AGE_BIN'] == filter_age_bin]
    if filter_career_bin != '전체':
        filtered_df = filtered_df[filtered_df['CAREER_BIN'] == filter_career_bin]
    if filter_salary_bin != '전체':
        filtered_df = filtered_df[filtered_df['SALARY_BIN'] == filter_salary_bin]
    if filter_region != '전체':
        filtered_df = filtered_df[filtered_df['REGION_CATEGORY'] == filter_region]
    if filter_contract != '전체':
        filtered_df = filtered_df[filtered_df['CONT_CATEGORY'] == filter_contract]

    filtered_emp_ids = filtered_df['EMP_ID'].unique()
    if len(filtered_emp_ids) == 0:
        return {"analysis_df": pd.DataFrame(), "order_map": order_map}

    # 3. 필터링된 직원들의 주말 근무 데이터 계산
    base_data = load_all_base_data()
    detailed_work_info_df = base_data["detailed_work_info_df"]

    work_records = detailed_work_info_df[detailed_work_info_df['EMP_ID'].isin(filtered_emp_ids)].copy()
    work_records['DATE'] = pd.to_datetime(work_records['DATE'])
    work_records['DAY_OF_WEEK'] = work_records['DATE'].dt.weekday
    
    weekend_work_df = work_records[
        (~work_records['WORK_ETC'].isin(['휴가', '주말 휴무', '비번', '휴무'])) &
        (work_records['DAY_OF_WEEK'] >= 5) # 5: Saturday, 6: Sunday
    ].copy()
    
    # 주말 근무 기록이 전혀 없는 경우, 모든 값을 0으로 채운 analysis_df 반환
    if weekend_work_df.empty:
        analysis_df = filtered_df.copy()
        analysis_df['WEEKEND_WORK_DAYS'] = 0
        return {"analysis_df": analysis_df, "order_map": order_map}

    weekend_work_df['PAY_PERIOD'] = weekend_work_df['DATE'].dt.strftime('%Y-%m')
    
    # 개인별 월평균 주말 근무일수 계산
    monthly_weekend_days = weekend_work_df.groupby(['EMP_ID', 'PAY_PERIOD']).size().reset_index(name='WEEKEND_WORK_DAYS')
    avg_weekend_days = monthly_weekend_days.groupby('EMP_ID')['WEEKEND_WORK_DAYS'].mean().reset_index()

    # 4. 최종 분석 데이터프레임 생성
    # 필터링된 직원 정보에, 계산된 월평균 주말 근무일수를 병합
    analysis_df = pd.merge(filtered_df, avg_weekend_days, on='EMP_ID', how='left')
    # WEEKEND_WORK_DAYS 컬럼에만 fillna(0)을 적용합니다.
    analysis_df['WEEKEND_WORK_DAYS'] = analysis_df['WEEKEND_WORK_DAYS'].fillna(0)

    return {"analysis_df": analysis_df, "order_map": order_map}

@st.cache_data
def prepare_proposal_17_data(
    filter_division='전체',
    filter_job_l1='전체',
    filter_position='전체',
    filter_gender='전체',
    filter_age_bin='전체',
    filter_career_bin='전체',
    filter_salary_bin='전체',
    filter_region='전체',
    filter_contract='전체'
):
    """
    제안 17: 조직의 주간 리듬 분석 (요일별 업무 강도 및 휴가 패턴)
    글로벌 필터를 적용하여, 분석에 필요한 3종의 상세 데이터를 생성합니다.
    """
    # 1. 필요한 모든 기본 데이터 로드
    base_data = load_all_base_data()
    emp_df = base_data["emp_df"]
    department_info_df = base_data["department_info_df"]
    job_info_df = base_data["job_info_df"]
    position_info_df = base_data["position_info_df"]
    career_info_df = base_data["career_info_df"]
    salary_contract_info_df = base_data["salary_contract_info_df"]
    region_info_df = base_data["region_info_df"]
    contract_info_df = base_data["contract_info_df"]
    department_df = base_data["department_df"]
    job_df = base_data["job_df"]
    position_df = base_data["position_df"]
    region_df = base_data["region_df"]
    daily_work_info_df = base_data["daily_work_info_df"]
    detailed_work_info_df = base_data["detailed_work_info_df"]
    detailed_leave_info_df = base_data["detailed_leave_info_df"]
    leave_type_df = base_data["leave_type_df"]
    work_info_df = base_data["work_info_df"]

    # 2. 글로벌 필터링을 위한 마스터 직원 테이블 생성
    emp_details = emp_df[['EMP_ID', 'GENDER', 'PERSONAL_ID', 'DURATION', 'IN_DATE', 'OUT_DATE']].copy()
    emp_details['GENDER'] = emp_details['GENDER'].map({'M': '남성', 'F': '여성'})
    emp_details['AGE'] = emp_details['PERSONAL_ID'].apply(calculate_age)
    emp_details['TENURE_YEARS'] = emp_details['DURATION'] / 365.25
    
    first_dept = department_info_df.sort_values('DEP_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_job = job_info_df.sort_values('JOB_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_pos = position_info_df.sort_values('GRADE_START_DATE').groupby('EMP_ID').first().reset_index()
    last_contract = contract_info_df.sort_values('CONT_START_DATE').groupby('EMP_ID').last().reset_index()
    last_region = region_info_df.sort_values('REG_APP_START_DATE').groupby('EMP_ID').last().reset_index()
    last_salary = salary_contract_info_df.sort_values('SAL_START_DATE').groupby('EMP_ID').last().reset_index()
    prior_career_summary = (career_info_df.groupby('EMP_ID')['CAREER_DURATION'].sum() / 365.25).reset_index(name='TOTAL_PRIOR_CAREER_YEARS')

    dept_level_map = department_df.set_index('DEP_ID')['DEP_LEVEL'].to_dict()
    parent_map_dept = department_df.set_index('DEP_ID')['UP_DEP_ID'].to_dict()
    dept_name_map = department_df.set_index('DEP_ID')['DEP_NAME'].to_dict()
    job_df_indexed = job_df.set_index('JOB_ID')
    parent_map_job = job_df_indexed['UP_JOB_ID'].to_dict()
    job_name_map = job_df.set_index('JOB_ID')['JOB_NAME'].to_dict()

    first_dept['DIVISION_NAME'] = first_dept['DEP_ID'].apply(lambda x: find_division_name_for_dept(x, dept_level_map, parent_map_dept, dept_name_map))
    first_job['JOB_L1_NAME'] = first_job['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    first_pos = pd.merge(first_pos, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID')
    last_region = pd.merge(last_region, region_df[['REG_ID', 'REG_NAME', 'DOMESTIC_YN']], on='REG_ID', how='left')
    last_region['REGION_CATEGORY'] = '해외 현장'; last_region.loc[last_region['DOMESTIC_YN'] == 'Y', 'REGION_CATEGORY'] = '국내 현장'; last_region.loc[last_region['REG_NAME'] == '서울특별시', 'REGION_CATEGORY'] = '서울 본사'
    
    emp_details = pd.merge(emp_details, first_dept[['EMP_ID', 'DIVISION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_job[['EMP_ID', 'JOB_L1_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_pos[['EMP_ID', 'POSITION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_contract[['EMP_ID', 'CONT_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_region[['EMP_ID', 'REGION_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_salary[['EMP_ID', 'SAL_AMOUNT', 'PAY_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, prior_career_summary, on='EMP_ID', how='left')
    emp_details['TOTAL_PRIOR_CAREER_YEARS'] = emp_details['TOTAL_PRIOR_CAREER_YEARS'].fillna(0)
    emp_details['TOTAL_CAREER_YEARS'] = emp_details['TENURE_YEARS'] + emp_details['TOTAL_PRIOR_CAREER_YEARS']
    
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    emp_details['SALARY_BIN'] = pd.cut(emp_details['ANNUAL_SALARY'], bins=salary_bins, labels=salary_labels, right=False)

    # 3. 글로벌 필터 적용
    filtered_emps_df = emp_details.copy()
    if filter_division != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['DIVISION_NAME'] == filter_division]
    if filter_job_l1 != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['JOB_L1_NAME'] == filter_job_l1]
    if filter_position != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['POSITION_NAME'] == filter_position]
    if filter_gender != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['GENDER'] == filter_gender]
    if filter_age_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['AGE_BIN'] == filter_age_bin]
    if filter_career_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CAREER_BIN'] == filter_career_bin]
    if filter_salary_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['SALARY_BIN'] == filter_salary_bin]
    if filter_region != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['REGION_CATEGORY'] == filter_region]
    if filter_contract != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CONT_CATEGORY'] == filter_contract]
    
    filtered_emp_ids = filtered_emps_df['EMP_ID'].unique()
    if len(filtered_emp_ids) == 0:
        return {"overtime_df": pd.DataFrame(), "leave_df": pd.DataFrame(), "workable_days_df": pd.DataFrame(), "order_map": order_map}

    # 4. 필터링된 직원 대상, 주간 리듬 분석 데이터 생성
    start_date_filter = pd.to_datetime('2022-01-01')
    normal_work_emp_ids = work_info_df[work_info_df['WORK_SYS_ID'] == 'WS001']['EMP_ID'].unique()
    target_emp_ids = np.intersect1d(normal_work_emp_ids, filtered_emp_ids)
    
    pos_info_sorted = position_info_df.sort_values('GRADE_START_DATE')
    job_info_sorted = job_info_df.sort_values('JOB_APP_START_DATE')
    dept_info_sorted = department_info_df.sort_values('DEP_APP_START_DATE')

    # 헬퍼 함수: 시점별 속성 정보 부여
    def add_point_in_time_attributes(df):
        df_sorted = df.sort_values('DATE')
        df_merged = pd.merge_asof(df_sorted, dept_info_sorted, left_on='DATE', right_on='DEP_APP_START_DATE', by='EMP_ID', direction='backward')
        df_merged = pd.merge_asof(df_merged, job_info_sorted, left_on='DATE', right_on='JOB_APP_START_DATE', by='EMP_ID', direction='backward')
        df_merged = pd.merge_asof(df_merged, pos_info_sorted, left_on='DATE', right_on='GRADE_START_DATE', by='EMP_ID', direction='backward')
        
        parent_info = df_merged['DEP_ID'].apply(lambda x: find_parents(x, dept_level_map, parent_map_dept, dept_name_map))
        df_merged = pd.concat([df_merged, parent_info], axis=1)
        df_merged['JOB_L1_NAME'] = df_merged['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
        df_merged['JOB_L2_NAME'] = df_merged['JOB_ID'].apply(lambda x: job_name_map.get(get_level2_ancestor(x, job_df_indexed, parent_map_job)))
        df_merged = pd.merge(df_merged, position_df[['POSITION_ID', 'POSITION_NAME']], on='POSITION_ID', how='left')

        attrs_to_merge = ['EMP_ID', 'GENDER', 'AGE_BIN', 'CAREER_BIN', 'SALARY_BIN', 'REGION_CATEGORY', 'CONT_CATEGORY']
        emp_attrs = filtered_emps_df[attrs_to_merge].drop_duplicates(subset=['EMP_ID'])
        df_merged = pd.merge(df_merged, emp_attrs, on='EMP_ID', how='left')
        
        return df_merged.dropna(subset=['DIVISION_NAME', 'JOB_L1_NAME', 'POSITION_NAME'])

    # 초과근무 데이터
    overtime_df = daily_work_info_df[(daily_work_info_df['EMP_ID'].isin(target_emp_ids)) & (pd.to_datetime(daily_work_info_df['DATE']) >= start_date_filter)].copy()
    overtime_df['DAY_OF_WEEK'] = overtime_df['DATE'].dt.day_name()
    overtime_df = add_point_in_time_attributes(overtime_df)

    # 연차휴가 데이터
    annual_leave_id = leave_type_df[leave_type_df['LEAVE_TYPE_NAME'] == '연차휴가']['LEAVE_TYPE_ID'].iloc[0]
    leave_df = detailed_leave_info_df[(detailed_leave_info_df['LEAVE_TYPE_ID'] == annual_leave_id) & (detailed_leave_info_df['EMP_ID'].isin(target_emp_ids)) & (pd.to_datetime(detailed_leave_info_df['DATE']) >= start_date_filter)].copy()
    leave_df['DAY_OF_WEEK'] = leave_df['DATE'].dt.day_name()
    leave_df = add_point_in_time_attributes(leave_df)

    # 총 근무일 데이터 (분모 계산용)
    workable_days_df = detailed_work_info_df[(~detailed_work_info_df['WORK_ETC'].isin(['휴가', '주말 휴무', '비번', '휴무'])) & (detailed_work_info_df['EMP_ID'].isin(target_emp_ids)) & (pd.to_datetime(detailed_work_info_df['DATE']) >= start_date_filter)].copy()
    workable_days_df['DAY_OF_WEEK'] = workable_days_df['DATE'].dt.day_name()
    workable_days_df = add_point_in_time_attributes(workable_days_df)

    # 5. 분석에서 특정 연령대 제외
    age_filter = ['20세 미만', '50세 이상']
    overtime_df = overtime_df[~overtime_df['AGE_BIN'].isin(age_filter)]
    leave_df = leave_df[~leave_df['AGE_BIN'].isin(age_filter)]
    workable_days_df = workable_days_df[~workable_days_df['AGE_BIN'].isin(age_filter)]

    return {
        "overtime_df": overtime_df, 
        "leave_df": leave_df, 
        "workable_days_df": workable_days_df,
        "order_map": order_map
    }

@st.cache_data
def prepare_proposal_18_data(
    filter_division='전체',
    filter_job_l1='전체',
    filter_position='전체',
    filter_gender='전체',
    filter_age_bin='전체',
    filter_career_bin='전체',
    filter_salary_bin='전체',
    filter_region='전체',
    filter_contract='전체'
):
    """
    제안 18: 직원 번아웃 신호 감지 (연차-병가 사용 패턴 분석)
    글로벌 필터를 적용하여 분석 대상을 선정한 뒤, "모든 연도"의 연차/병가 사용 패턴 데이터를 생성합니다.
    """
    # 1. 필요한 모든 기본 데이터 로드
    base_data = load_all_base_data()
    emp_df = base_data["emp_df"]
    department_info_df = base_data["department_info_df"]
    job_info_df = base_data["job_info_df"]
    position_info_df = base_data["position_info_df"]
    career_info_df = base_data["career_info_df"]
    salary_contract_info_df = base_data["salary_contract_info_df"]
    region_info_df = base_data["region_info_df"]
    contract_info_df = base_data["contract_info_df"]
    department_df = base_data["department_df"]
    job_df = base_data["job_df"]
    position_df = base_data["position_df"]
    region_df = base_data["region_df"]
    detailed_leave_info_df = base_data["detailed_leave_info_df"]
    leave_type_df = base_data["leave_type_df"]

    # 2. 글로벌 필터링을 위한 마스터 직원 테이블 생성
    emp_details = emp_df[['EMP_ID', 'NAME', 'GENDER', 'PERSONAL_ID', 'DURATION', 'IN_DATE', 'OUT_DATE']].copy()
    emp_details['GENDER'] = emp_details['GENDER'].map({'M': '남성', 'F': '여성'})
    emp_details['AGE'] = emp_details['PERSONAL_ID'].apply(calculate_age)
    emp_details['TENURE_YEARS'] = emp_details['DURATION'] / 365.25
    
    first_dept = department_info_df.sort_values('DEP_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_job = job_info_df.sort_values('JOB_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_pos = position_info_df.sort_values('GRADE_START_DATE').groupby('EMP_ID').first().reset_index()
    last_contract = contract_info_df.sort_values('CONT_START_DATE').groupby('EMP_ID').last().reset_index()
    last_region = region_info_df.sort_values('REG_APP_START_DATE').groupby('EMP_ID').last().reset_index()
    last_salary = salary_contract_info_df.sort_values('SAL_START_DATE').groupby('EMP_ID').last().reset_index()
    prior_career_summary = (career_info_df.groupby('EMP_ID')['CAREER_DURATION'].sum() / 365.25).reset_index(name='TOTAL_PRIOR_CAREER_YEARS')

    dept_level_map = department_df.set_index('DEP_ID')['DEP_LEVEL'].to_dict()
    parent_map_dept = department_df.set_index('DEP_ID')['UP_DEP_ID'].to_dict()
    dept_name_map = department_df.set_index('DEP_ID')['DEP_NAME'].to_dict()
    job_df_indexed = job_df.set_index('JOB_ID')
    parent_map_job = job_df_indexed['UP_JOB_ID'].to_dict()
    job_name_map = job_df.set_index('JOB_ID')['JOB_NAME'].to_dict()

    first_dept['DIVISION_NAME'] = first_dept['DEP_ID'].apply(lambda x: find_division_name_for_dept(x, dept_level_map, parent_map_dept, dept_name_map))
    first_job['JOB_L1_NAME'] = first_job['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    first_pos = pd.merge(first_pos, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID')
    last_region = pd.merge(last_region, region_df[['REG_ID', 'REG_NAME', 'DOMESTIC_YN']], on='REG_ID', how='left')
    last_region['REGION_CATEGORY'] = '해외 현장'; last_region.loc[last_region['DOMESTIC_YN'] == 'Y', 'REGION_CATEGORY'] = '국내 현장'; last_region.loc[last_region['REG_NAME'] == '서울특별시', 'REGION_CATEGORY'] = '서울 본사'
    
    emp_details = pd.merge(emp_details, first_dept[['EMP_ID', 'DIVISION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_job[['EMP_ID', 'JOB_L1_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_pos[['EMP_ID', 'POSITION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_contract[['EMP_ID', 'CONT_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_region[['EMP_ID', 'REGION_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_salary[['EMP_ID', 'SAL_AMOUNT', 'PAY_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, prior_career_summary, on='EMP_ID', how='left')
    emp_details['TOTAL_PRIOR_CAREER_YEARS'] = emp_details['TOTAL_PRIOR_CAREER_YEARS'].fillna(0)
    emp_details['TOTAL_CAREER_YEARS'] = emp_details['TENURE_YEARS'] + emp_details['TOTAL_PRIOR_CAREER_YEARS']
    
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    emp_details['SALARY_BIN'] = pd.cut(emp_details['ANNUAL_SALARY'], bins=salary_bins, labels=salary_labels, right=False)

    # 3. 글로벌 필터 적용
    filtered_emps_df = emp_details.copy()
    if filter_division != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['DIVISION_NAME'] == filter_division]
    if filter_job_l1 != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['JOB_L1_NAME'] == filter_job_l1]
    if filter_position != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['POSITION_NAME'] == filter_position]
    if filter_gender != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['GENDER'] == filter_gender]
    if filter_age_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['AGE_BIN'] == filter_age_bin]
    if filter_career_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CAREER_BIN'] == filter_career_bin]
    if filter_salary_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['SALARY_BIN'] == filter_salary_bin]
    if filter_region != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['REGION_CATEGORY'] == filter_region]
    if filter_contract != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CONT_CATEGORY'] == filter_contract]
    
    filtered_emp_ids = filtered_emps_df['EMP_ID'].unique()
    if len(filtered_emp_ids) == 0:
        return {"analysis_df": pd.DataFrame(), "order_map": order_map}

    # 4. 필터링된 직원들의 연차/병가 데이터 준비
    leave_df = detailed_leave_info_df[detailed_leave_info_df['EMP_ID'].isin(filtered_emp_ids)].copy()
    leave_df = pd.merge(leave_df, leave_type_df, on='LEAVE_TYPE_ID')
    leave_df['DATE'] = pd.to_datetime(leave_df['DATE'])
    leave_df['YEAR'] = leave_df['DATE'].dt.year
    
    leave_summary = leave_df.groupby(['YEAR', 'EMP_ID', 'LEAVE_TYPE_NAME'])['LEAVE_LENGTH'].sum().unstack(fill_value=0).reset_index()
    required_leave_types = ['연차휴가', '병휴가']
    for leave_type in required_leave_types:
        if leave_type not in leave_summary.columns: leave_summary[leave_type] = 0

    # 5. 모든 연도/직원에 대한 뼈대(Scaffold) 생성 후 데이터 병합
    scaffold_records = []
    
    filtered_emps_for_scaffold = emp_df[emp_df['EMP_ID'].isin(filtered_emp_ids)]
    if filtered_emps_for_scaffold.empty:
         return {"analysis_df": pd.DataFrame(), "order_map": order_map}
         
    analysis_years_list = range(filtered_emps_for_scaffold['IN_DATE'].min().year, datetime.datetime.now().year + 1)
    
    for year in analysis_years_list:
        year_start, year_end = pd.to_datetime(f'{year}-01-01'), pd.to_datetime(f'{year}-12-31')
        
        active_emps_in_year = filtered_emps_for_scaffold[
            (filtered_emps_for_scaffold['IN_DATE'] <= year_end) & 
            (filtered_emps_for_scaffold['OUT_DATE'].isnull() | (filtered_emps_for_scaffold['OUT_DATE'] >= year_start))
        ]['EMP_ID'].unique()
        
        for emp_id in active_emps_in_year:
            scaffold_records.append({'YEAR': year, 'EMP_ID': emp_id})
            
    scaffold_df = pd.DataFrame(scaffold_records)
    if scaffold_df.empty:
        return {"analysis_df": pd.DataFrame(), "order_map": order_map}
    
    analysis_df = pd.merge(scaffold_df, leave_summary, on=['YEAR', 'EMP_ID'], how='left')
    analysis_df[required_leave_types] = analysis_df[required_leave_types].fillna(0)

    # 6. 분석에 필요한 추가 정보(이름, 부서 등) 병합
    cols_to_merge = [
        'EMP_ID', 'NAME', 'DIVISION_NAME', 'JOB_L1_NAME', 'POSITION_NAME',
        'GENDER', 'AGE_BIN', 'CAREER_BIN', 'SALARY_BIN', 'REGION_CATEGORY', 'CONT_CATEGORY'
    ]
    # filtered_emps_df에서 중복 제거
    emp_attrs = filtered_emps_df[cols_to_merge].drop_duplicates(subset=['EMP_ID'])
    analysis_df = pd.merge(analysis_df, emp_attrs, on='EMP_ID', how='left')
    
    # 7. 지터링(Jittering)을 위한 데이터 추가
    jitter_strength = 0.15
    num_points = len(analysis_df)
    np.random.seed(42)
    analysis_df['연차휴가_jitter'] = analysis_df['연차휴가'] + np.random.uniform(-jitter_strength, jitter_strength, num_points)
    analysis_df['병휴가_jitter'] = analysis_df['병휴가'] + np.random.uniform(-jitter_strength, jitter_strength, num_points)
    
    analysis_df = analysis_df.dropna(subset=['DIVISION_NAME', 'JOB_L1_NAME', 'POSITION_NAME'])

    return {"analysis_df": analysis_df, "order_map": order_map}

@st.cache_data
def prepare_proposal_19_data(
    filter_division='전체',
    filter_job_l1='전체',
    filter_position='전체',
    filter_gender='전체',
    filter_age_bin='전체',
    filter_career_bin='전체',
    filter_salary_bin='전체',
    filter_region='전체',
    filter_contract='전체'
):
    """
    제안 19: 퇴사 예측 선행 지표 분석 (퇴사 직전 휴가 사용 패턴)
    글로벌 필터를 적용하여, 모든 차원의 퇴사자/재직자 휴가 사용 패턴 데이터를 생성합니다.
    """
    # 1. 필요한 모든 기본 데이터 로드
    base_data = load_all_base_data()
    emp_df = base_data["emp_df"]
    department_info_df = base_data["department_info_df"]
    job_info_df = base_data["job_info_df"]
    position_info_df = base_data["position_info_df"]
    career_info_df = base_data["career_info_df"]
    salary_contract_info_df = base_data["salary_contract_info_df"]
    region_info_df = base_data["region_info_df"]
    contract_info_df = base_data["contract_info_df"]
    department_df = base_data["department_df"]
    job_df = base_data["job_df"]
    position_df = base_data["position_df"]
    region_df = base_data["region_df"]
    detailed_leave_info_df = base_data["detailed_leave_info_df"]
    leave_type_df = base_data["leave_type_df"]

    # 2. 글로벌 필터링을 위한 마스터 직원 테이블 생성
    emp_details = emp_df[['EMP_ID', 'GENDER', 'PERSONAL_ID', 'DURATION', 'IN_DATE', 'OUT_DATE', 'CURRENT_EMP_YN']].copy()
    emp_details['GENDER'] = emp_details['GENDER'].map({'M': '남성', 'F': '여성'})
    emp_details['AGE'] = emp_details['PERSONAL_ID'].apply(calculate_age)
    emp_details['TENURE_YEARS'] = emp_details['DURATION'] / 365.25
    
    first_dept = department_info_df.sort_values('DEP_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_job = job_info_df.sort_values('JOB_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_pos = position_info_df.sort_values('GRADE_START_DATE').groupby('EMP_ID').first().reset_index()
    last_contract = contract_info_df.sort_values('CONT_START_DATE').groupby('EMP_ID').last().reset_index()
    last_region = region_info_df.sort_values('REG_APP_START_DATE').groupby('EMP_ID').last().reset_index()
    last_salary = salary_contract_info_df.sort_values('SAL_START_DATE').groupby('EMP_ID').last().reset_index()
    prior_career_summary = (career_info_df.groupby('EMP_ID')['CAREER_DURATION'].sum() / 365.25).reset_index(name='TOTAL_PRIOR_CAREER_YEARS')

    dept_level_map = department_df.set_index('DEP_ID')['DEP_LEVEL'].to_dict()
    parent_map_dept = department_df.set_index('DEP_ID')['UP_DEP_ID'].to_dict()
    dept_name_map = department_df.set_index('DEP_ID')['DEP_NAME'].to_dict()
    job_df_indexed = job_df.set_index('JOB_ID')
    parent_map_job = job_df_indexed['UP_JOB_ID'].to_dict()
    job_name_map = job_df.set_index('JOB_ID')['JOB_NAME'].to_dict()

    first_dept['DIVISION_NAME'] = first_dept['DEP_ID'].apply(lambda x: find_division_name_for_dept(x, dept_level_map, parent_map_dept, dept_name_map))
    first_job['JOB_L1_NAME'] = first_job['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    first_pos = pd.merge(first_pos, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID')
    last_region = pd.merge(last_region, region_df[['REG_ID', 'REG_NAME', 'DOMESTIC_YN']], on='REG_ID', how='left')
    last_region['REGION_CATEGORY'] = '해외 현장'; last_region.loc[last_region['DOMESTIC_YN'] == 'Y', 'REGION_CATEGORY'] = '국내 현장'; last_region.loc[last_region['REG_NAME'] == '서울특별시', 'REGION_CATEGORY'] = '서울 본사'
    
    emp_details = pd.merge(emp_details, first_dept[['EMP_ID', 'DIVISION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_job[['EMP_ID', 'JOB_L1_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_pos[['EMP_ID', 'POSITION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_contract[['EMP_ID', 'CONT_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_region[['EMP_ID', 'REGION_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_salary[['EMP_ID', 'SAL_AMOUNT', 'PAY_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, prior_career_summary, on='EMP_ID', how='left')
    emp_details['TOTAL_PRIOR_CAREER_YEARS'] = emp_details['TOTAL_PRIOR_CAREER_YEARS'].fillna(0)
    emp_details['TOTAL_CAREER_YEARS'] = emp_details['TENURE_YEARS'] + emp_details['TOTAL_PRIOR_CAREER_YEARS']
    
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    emp_details['SALARY_BIN'] = pd.cut(emp_details['ANNUAL_SALARY'], bins=salary_bins, labels=salary_labels, right=False)

    # 3. 글로벌 필터 적용
    filtered_emps_df = emp_details.copy()
    if filter_division != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['DIVISION_NAME'] == filter_division]
    if filter_job_l1 != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['JOB_L1_NAME'] == filter_job_l1]
    if filter_position != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['POSITION_NAME'] == filter_position]
    if filter_gender != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['GENDER'] == filter_gender]
    if filter_age_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['AGE_BIN'] == filter_age_bin]
    if filter_career_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CAREER_BIN'] == filter_career_bin]
    if filter_salary_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['SALARY_BIN'] == filter_salary_bin]
    if filter_region != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['REGION_CATEGORY'] == filter_region]
    if filter_contract != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CONT_CATEGORY'] == filter_contract]

    # 3-1. 분석에서 특정 연령대 제외
    age_filter = ['20세 미만', '50세 이상']
    filtered_emps_df = filtered_emps_df[~filtered_emps_df['AGE_BIN'].isin(age_filter)]
    
    filtered_emp_ids = filtered_emps_df['EMP_ID'].unique()
    if len(filtered_emp_ids) == 0:
        return {"leavers_df": pd.DataFrame(), "stayers_df": pd.DataFrame(), "order_map": order_map}

    # 4. 필터링된 직원들의 휴가 데이터 준비
    leave_df = pd.merge(detailed_leave_info_df, leave_type_df, on='LEAVE_TYPE_ID')
    leave_df = leave_df[leave_df['EMP_ID'].isin(filtered_emp_ids)].copy()
    leave_df['DATE'] = pd.to_datetime(leave_df['DATE'])
    leave_df['LEAVE_LENGTH'] = pd.to_numeric(leave_df['LEAVE_LENGTH'])

    # 5. 퇴사자(Leavers) 그룹 패턴 계산
    leavers_base = filtered_emps_df[filtered_emps_df['CURRENT_EMP_YN'] == 'N'].copy()
    leaver_leave_data = pd.merge(leavers_base, leave_df, on='EMP_ID', how='left')
    leaver_leave_data = leaver_leave_data[
        (leaver_leave_data['DATE'] < leaver_leave_data['OUT_DATE']) &
        (leaver_leave_data['DATE'] >= (leaver_leave_data['OUT_DATE'] - pd.DateOffset(months=12)))
    ].copy()
    
    if not leaver_leave_data.empty:
        leaver_leave_data['MONTHS_BEFORE_LEAVING'] = (leaver_leave_data['OUT_DATE'].dt.to_period('M') - leaver_leave_data['DATE'].dt.to_period('M')).apply(lambda x: x.n)
        leaver_leave_data = leaver_leave_data[leaver_leave_data['MONTHS_BEFORE_LEAVING'] >= 0]
    
    # 6. 재직자(Stayers) 그룹 기준선(Baseline) 계산 (최근 1년 기준)
    stayers_base = filtered_emps_df[filtered_emps_df['CURRENT_EMP_YN'] == 'Y'].copy()
    end_date_stayers = datetime.datetime.now()
    start_date_stayers = end_date_stayers - pd.DateOffset(months=12)
    
    stayer_leaves = leave_df[
        (leave_df['EMP_ID'].isin(stayers_base['EMP_ID'])) &
        (leave_df['DATE'] >= start_date_stayers) &
        (leave_df['DATE'] <= end_date_stayers)
    ].copy()
    stayer_leaves = pd.merge(stayer_leaves, stayers_base, on='EMP_ID', how='left')
    
    # 7. 모든 차원에 대해 집계
    leaver_records = []
    stayer_records = []
    
    dimensions = [
        'DIVISION_NAME', 'JOB_L1_NAME', 'POSITION_NAME', 'GENDER', 
        'AGE_BIN', 'CAREER_BIN', 'SALARY_BIN', 'REGION_CATEGORY', 'CONT_CATEGORY'
    ]
    
    # '전체' 데이터 추가
    leaver_pattern_overall = leaver_leave_data.groupby('MONTHS_BEFORE_LEAVING')['LEAVE_LENGTH'].sum() / leaver_leave_data['EMP_ID'].nunique()
    stayer_baseline_overall = stayer_leaves['LEAVE_LENGTH'].sum() / stayers_base['EMP_ID'].nunique() / 12 if not stayers_base.empty else 0

    for month, rate in leaver_pattern_overall.items():
        leaver_records.append({'GROUP_TYPE': '전체', 'GROUP_NAME': '전체', 'MONTHS_BEFORE_LEAVING': month, 'LEAVE_DAYS_AVG': rate})
    stayer_records.append({'GROUP_TYPE': '전체', 'GROUP_NAME': '전체', 'BASELINE_LEAVE_DAYS': stayer_baseline_overall})

    # 각 차원별 데이터 추가
    for dim in dimensions:
        if dim not in leaver_leave_data.columns or dim not in stayer_leaves.columns:
            continue
            
        leaver_n_unique = leaver_leave_data.groupby(dim, observed=False)['EMP_ID'].nunique()
        stayer_n_unique = stayers_base.groupby(dim, observed=False)['EMP_ID'].nunique()
        
        leaver_pattern_dim = leaver_leave_data.groupby([dim, 'MONTHS_BEFORE_LEAVING'], observed=False)['LEAVE_LENGTH'].sum().reset_index()
        leaver_pattern_dim = pd.merge(leaver_pattern_dim, leaver_n_unique.rename('N_UNIQUE'), left_on=dim, right_index=True)
        leaver_pattern_dim['LEAVE_DAYS_AVG'] = leaver_pattern_dim['LEAVE_LENGTH'] / leaver_pattern_dim['N_UNIQUE']
        
        stayer_baseline_dim = (stayer_leaves.groupby(dim, observed=False)['LEAVE_LENGTH'].sum() / 12) / stayer_n_unique
        
        # DataFrame이 아닌 dict 형태로 leaver_records에 추가
        for _, row in leaver_pattern_dim.iterrows():
            leaver_records.append({
                'GROUP_TYPE': dim,
                'GROUP_NAME': row[dim],
                'MONTHS_BEFORE_LEAVING': row['MONTHS_BEFORE_LEAVING'],
                'LEAVE_DAYS_AVG': row['LEAVE_DAYS_AVG']
            })
        
        # Series를 dict로 변환하여 stayer_records에 추가
        for group_name, baseline_value in stayer_baseline_dim.items():
            stayer_records.append({
                'GROUP_TYPE': dim,
                'GROUP_NAME': group_name,
                'BASELINE_LEAVE_DAYS': baseline_value
            })

    # pd.concat 대신 pd.DataFrame()을 사용하여 딕셔너리 리스트로부터 생성
    final_leavers_df = pd.DataFrame(leaver_records).dropna(subset=['GROUP_NAME'])
    final_stayers_df = pd.DataFrame(stayer_records).dropna(subset=['GROUP_NAME'])
    
    return {
        "leavers_df": final_leavers_df, 
        "stayers_df": final_stayers_df, 
        "order_map": order_map
    }

@st.cache_data
def prepare_proposal_20_data(
    filter_division='전체',
    filter_job_l1='전체',
    filter_position='전체',
    filter_gender='전체',
    filter_age_bin='전체',
    filter_career_bin='전체',
    filter_salary_bin='전체',
    filter_region='전체',
    filter_contract='전체'
):
    """
    제안 20: 조직별 휴가 사용 패턴 분석 (Team별 휴가 유형 진단)
    글로벌 필터를 적용하여, '연차휴가'에 대한 모든 상세 데이터를 생성합니다.
    """
    # 1. 필요한 모든 기본 데이터 로드
    base_data = load_all_base_data()
    emp_df = base_data["emp_df"]
    department_info_df = base_data["department_info_df"]
    job_info_df = base_data["job_info_df"]
    position_info_df = base_data["position_info_df"]
    career_info_df = base_data["career_info_df"]
    salary_contract_info_df = base_data["salary_contract_info_df"]
    region_info_df = base_data["region_info_df"]
    contract_info_df = base_data["contract_info_df"]
    department_df = base_data["department_df"]
    job_df = base_data["job_df"]
    position_df = base_data["position_df"]
    region_df = base_data["region_df"]
    detailed_leave_info_df = base_data["detailed_leave_info_df"]
    leave_type_df = base_data["leave_type_df"]

    # 2. 글로벌 필터링을 위한 마스터 직원 테이블 생성
    emp_details = emp_df[['EMP_ID', 'GENDER', 'PERSONAL_ID', 'DURATION', 'IN_DATE', 'OUT_DATE']].copy()
    emp_details['GENDER'] = emp_details['GENDER'].map({'M': '남성', 'F': '여성'})
    emp_details['AGE'] = emp_details['PERSONAL_ID'].apply(calculate_age)
    emp_details['TENURE_YEARS'] = emp_details['DURATION'] / 365.25
    
    first_dept = department_info_df.sort_values('DEP_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_job = job_info_df.sort_values('JOB_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_pos = position_info_df.sort_values('GRADE_START_DATE').groupby('EMP_ID').first().reset_index()
    last_contract = contract_info_df.sort_values('CONT_START_DATE').groupby('EMP_ID').last().reset_index()
    last_region = region_info_df.sort_values('REG_APP_START_DATE').groupby('EMP_ID').last().reset_index()
    last_salary = salary_contract_info_df.sort_values('SAL_START_DATE').groupby('EMP_ID').last().reset_index()
    prior_career_summary = (career_info_df.groupby('EMP_ID')['CAREER_DURATION'].sum() / 365.25).reset_index(name='TOTAL_PRIOR_CAREER_YEARS')

    dept_level_map = department_df.set_index('DEP_ID')['DEP_LEVEL'].to_dict()
    parent_map_dept = department_df.set_index('DEP_ID')['UP_DEP_ID'].to_dict()
    dept_name_map = department_df.set_index('DEP_ID')['DEP_NAME'].to_dict()
    job_df_indexed = job_df.set_index('JOB_ID')
    parent_map_job = job_df_indexed['UP_JOB_ID'].to_dict()
    job_name_map = job_df.set_index('JOB_ID')['JOB_NAME'].to_dict()

    first_dept['DIVISION_NAME'] = first_dept['DEP_ID'].apply(lambda x: find_division_name_for_dept(x, dept_level_map, parent_map_dept, dept_name_map))
    first_job['JOB_L1_NAME'] = first_job['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    first_pos = pd.merge(first_pos, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID')
    last_region = pd.merge(last_region, region_df[['REG_ID', 'REG_NAME', 'DOMESTIC_YN']], on='REG_ID', how='left')
    last_region['REGION_CATEGORY'] = '해외 현장'; last_region.loc[last_region['DOMESTIC_YN'] == 'Y', 'REGION_CATEGORY'] = '국내 현장'; last_region.loc[last_region['REG_NAME'] == '서울특별시', 'REGION_CATEGORY'] = '서울 본사'
    
    emp_details = pd.merge(emp_details, first_dept[['EMP_ID', 'DIVISION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_job[['EMP_ID', 'JOB_L1_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_pos[['EMP_ID', 'POSITION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_contract[['EMP_ID', 'CONT_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_region[['EMP_ID', 'REGION_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_salary[['EMP_ID', 'SAL_AMOUNT', 'PAY_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, prior_career_summary, on='EMP_ID', how='left')
    emp_details['TOTAL_PRIOR_CAREER_YEARS'] = emp_details['TOTAL_PRIOR_CAREER_YEARS'].fillna(0)
    emp_details['TOTAL_CAREER_YEARS'] = emp_details['TENURE_YEARS'] + emp_details['TOTAL_PRIOR_CAREER_YEARS']
    
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    emp_details['SALARY_BIN'] = pd.cut(emp_details['ANNUAL_SALARY'], bins=salary_bins, labels=salary_labels, right=False)

    # 3. 글로벌 필터 적용
    filtered_emps_df = emp_details.copy()
    if filter_division != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['DIVISION_NAME'] == filter_division]
    if filter_job_l1 != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['JOB_L1_NAME'] == filter_job_l1]
    if filter_position != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['POSITION_NAME'] == filter_position]
    if filter_gender != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['GENDER'] == filter_gender]
    if filter_age_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['AGE_BIN'] == filter_age_bin]
    if filter_career_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CAREER_BIN'] == filter_career_bin]
    if filter_salary_bin != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['SALARY_BIN'] == filter_salary_bin]
    if filter_region != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['REGION_CATEGORY'] == filter_region]
    if filter_contract != '전체': filtered_emps_df = filtered_emps_df[filtered_emps_df['CONT_CATEGORY'] == filter_contract]
    
    filtered_emp_ids = filtered_emps_df['EMP_ID'].unique()
    if len(filtered_emp_ids) == 0:
        return {"analysis_df": pd.DataFrame(), "order_map": order_map}

    # 4. 필터링된 직원들의 '연차휴가' 데이터에 모든 시점별 속성 정보 부여
    annual_leave_id = leave_type_df[leave_type_df['LEAVE_TYPE_NAME'] == '연차휴가']['LEAVE_TYPE_ID'].iloc[0]
    analysis_df = detailed_leave_info_df[
        (detailed_leave_info_df['LEAVE_TYPE_ID'] == annual_leave_id) &
        (detailed_leave_info_df['EMP_ID'].isin(filtered_emp_ids))
    ].copy()
    analysis_df['DATE'] = pd.to_datetime(analysis_df['DATE'])
    
    # --- [수정된 부분 1: YEAR 컬럼 추가 및 2020년 이후 필터링] ---
    analysis_df['YEAR'] = analysis_df['DATE'].dt.year
    analysis_df = analysis_df[analysis_df['YEAR'] >= 2020].copy()
    # --- [수정된 부분 끝] ---
    
    if analysis_df.empty:
        return {"analysis_df": pd.DataFrame(), "order_map": order_map}

    # 정렬된 이력 테이블 준비
    dept_info_sorted = department_info_df.sort_values('DEP_APP_START_DATE')
    job_info_sorted = job_info_df.sort_values('JOB_APP_START_DATE')
    pos_info_with_name = pd.merge(position_info_df, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID')
    pos_info_sorted = pos_info_with_name.sort_values('GRADE_START_DATE')

    analysis_df = analysis_df.sort_values('DATE')
    
    # 시점별 부서, 직무, 직위 정보 병합
    analysis_df = pd.merge_asof(analysis_df, dept_info_sorted, left_on='DATE', right_on='DEP_APP_START_DATE', by='EMP_ID', direction='backward')
    analysis_df = pd.merge_asof(analysis_df, job_info_sorted, left_on='DATE', right_on='JOB_APP_START_DATE', by='EMP_ID', direction='backward')
    analysis_df = pd.merge_asof(analysis_df, pos_info_sorted, left_on='DATE', right_on='GRADE_START_DATE', by='EMP_ID', direction='backward')

    # 이름(Label) 정보 추가
    parent_info = analysis_df['DEP_ID'].apply(lambda x: find_parents(x, dept_level_map, parent_map_dept, dept_name_map))
    analysis_df = pd.concat([analysis_df, parent_info], axis=1)
    analysis_df['JOB_L1_NAME'] = analysis_df['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    analysis_df['JOB_L2_NAME'] = analysis_df['JOB_ID'].apply(lambda x: job_name_map.get(get_level2_ancestor(x, job_df_indexed, parent_map_job)))
    analysis_df = pd.merge(analysis_df, department_df[['DEP_ID', 'DEP_NAME']].rename(columns={'DEP_NAME': 'TEAM_NAME'}), on='DEP_ID', how='left')
    
    # 나머지 정적/계산된 필터 속성 정보 병합
    attrs_to_merge = ['EMP_ID', 'GENDER', 'AGE_BIN', 'CAREER_BIN', 'SALARY_BIN', 'REGION_CATEGORY', 'CONT_CATEGORY']
    emp_attrs = filtered_emps_df[attrs_to_merge].drop_duplicates(subset=['EMP_ID'])
    analysis_df = pd.merge(analysis_df, emp_attrs, on='EMP_ID', how='left')
    
    # [수정] dropna에서 TEAM_NAME을 포함한 필수 컬럼만 남김
    analysis_df = analysis_df.dropna(subset=['DIVISION_NAME', 'TEAM_NAME'])

    # 5. 휴가 패턴 컬럼 생성
    analysis_df['DAY_OF_WEEK'] = analysis_df['DATE'].dt.weekday
    analysis_df['IS_BRIDGE'] = analysis_df['DAY_OF_WEEK'].isin([0, 4]) # 0: Monday, 4: Friday

    analysis_df = analysis_df.sort_values(['EMP_ID', 'DATE'])
    analysis_df['DATE_DIFF'] = analysis_df.groupby('EMP_ID')['DATE'].diff().dt.days
    analysis_df['BLOCK_ID'] = (analysis_df['DATE_DIFF'] != 1).cumsum()
    block_lengths = analysis_df.groupby(['EMP_ID', 'BLOCK_ID'])['DATE'].transform('count')
    analysis_df['IS_LONG_LEAVE'] = block_lengths >= 3

    return {"analysis_df": analysis_df, "order_map": order_map}

# 각 함수의 결과는 @st.cache_data로 캐싱되어야 합니다.