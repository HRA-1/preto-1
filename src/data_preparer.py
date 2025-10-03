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
    current_salaries = salary_contract_info_df[salary_contract_info_df['SAL_END_DATE'].isnull()][['EMP_ID', 'SAL_AMOUNT', 'PAY_CATEGORY']]
    
    # 4. 과거 총 경력 계산
    prior_career_summary = career_info_df.groupby('EMP_ID')['CAREER_DURATION'].sum().reset_index()
    prior_career_summary['TOTAL_PRIOR_CAREER_YEARS'] = prior_career_summary['CAREER_DURATION'] / 365.25

    # 5. 모든 정보 병합
    snapshot_df = pd.merge(snapshot_df, current_depts, on='EMP_ID', how='left')
    snapshot_df = pd.merge(snapshot_df, current_positions, on='EMP_ID', how='left')
    snapshot_df = pd.merge(snapshot_df, current_jobs, on='EMP_ID', how='left')
    snapshot_df = pd.merge(snapshot_df, current_salaries, on='EMP_ID', how='left')
    snapshot_df = pd.merge(snapshot_df, prior_career_summary[['EMP_ID', 'TOTAL_PRIOR_CAREER_YEARS']], on='EMP_ID', how='left')
    snapshot_df['TOTAL_PRIOR_CAREER_YEARS'] = snapshot_df['TOTAL_PRIOR_CAREER_YEARS'].fillna(0)
    
    # 6. 이름 정보 등 추가 (Labeling)
    parent_info = snapshot_df['DEP_ID'].apply(lambda x: find_parents(x, dept_level_map, parent_map_dept, dept_name_map))
    snapshot_df = pd.concat([snapshot_df, parent_info.set_index(snapshot_df.index)], axis=1)
    snapshot_df = pd.merge(snapshot_df, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID', how='left')
    snapshot_df['JOB_L1_NAME'] = snapshot_df['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    snapshot_df['JOB_L2_NAME'] = snapshot_df['JOB_ID'].apply(lambda x: job_name_map.get(get_level2_ancestor(x, job_df_indexed, parent_map_job)))

    # 7. 필터링을 위한 구간(Bin) 정보 추가
    # 연령대
    age_bins = [-1, 19, 29, 39, 49, 150]
    age_labels = ['20세 미만', '20-29세', '30-39세', '40-49세', '50세 이상']
    snapshot_df['AGE_BIN'] = pd.cut(snapshot_df['AGE'], bins=age_bins, labels=age_labels)

    # 근속년수
    tenure_bins_agg = [-np.inf, 3, 7, np.inf]
    tenure_labels_agg = ['3년 이하', '3년초과~7년이하', '7년 초과']
    snapshot_df['TENURE_GROUP'] = pd.cut(snapshot_df['TENURE_YEARS'], bins=tenure_bins_agg, labels=tenure_labels_agg)

    # 총 경력연차
    snapshot_df['TOTAL_CAREER_YEARS'] = snapshot_df['TENURE_YEARS'] + snapshot_df['TOTAL_PRIOR_CAREER_YEARS']
    career_bins = [-1, 1, 3, 7, 15, 150]
    career_labels = ['1년 미만', '1~3년', '3~7년', '7~15년', '15년 이상']
    snapshot_df['CAREER_BIN'] = pd.cut(snapshot_df['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    
    # 연봉 구간
    snapshot_df['ANNUAL_SALARY'] = snapshot_df['SAL_AMOUNT'] # 현재 연봉 기준만 있다고 가정
    salary_bins = [-1, 39999999, 59999999, 79999999, 99999999, float('inf')]
    salary_labels = ['4,000만원 미만', '4,000~5,999만원', '6,000~7,999만원', '8,000~9,999만원', '1억원 이상']
    snapshot_df['SALARY_BIN'] = pd.cut(snapshot_df['ANNUAL_SALARY'], bins=salary_bins, labels=salary_labels, right=False)

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
    analysis_df.loc[analysis_df['PAY_CATEGORY'] == '일급', 'ANNUAL_SALARY'] = analysis_df['SAL_AMOUNT'] * 250 # 일반적인 연간 근무일수(약 250일) 기준
    analysis_df.loc[analysis_df['PAY_CATEGORY'] == '시급', 'ANNUAL_SALARY'] = analysis_df['SAL_AMOUNT'] * 2080 # 통상시급 계산 기준 (주 40시간 * 52주)

    # 지역 카테고리
    region_names = region_df.set_index('REG_ID')['REG_NAME'].to_dict()
    analysis_df['REG_NAME'] = analysis_df['REG_ID'].map(region_names)
    analysis_df['REGION_CATEGORY'] = '해외 현장'
    analysis_df.loc[analysis_df['DOMESTIC_YN'] == 'Y', 'REGION_CATEGORY'] = '국내 현장'
    analysis_df.loc[analysis_df['REG_NAME'] == '서울특별시', 'REGION_CATEGORY'] = '서울 본사'
    
    # 성별
    analysis_df['GENDER'] = analysis_df['GENDER'].map({'M': '남성', 'F': '여성'})

    # 7. 필터링을 위한 구간(Bin) 정보 추가
    age_bins = [-1, 19, 29, 39, 49, 150]; age_labels = ['20세 미만', '20-29세', '30-39세', '40-49세', '50세 이상']
    analysis_df['AGE_BIN'] = pd.cut(analysis_df['AGE'], bins=age_bins, labels=age_labels)
    
    career_bins = [-1, 1, 3, 7, 15, 150]; career_labels = ['1년 미만', '1~3년', '3~7년', '7~15년', '15년 이상']
    analysis_df['CAREER_BIN'] = pd.cut(analysis_df['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    
    salary_bins = [-1, 39999999, 59999999, 79999999, 99999999, float('inf')]; salary_labels = ['4,000만원 미만', '4,000~5,999만원', '6,000~7,999만원', '8,000~9,999만원', '1억원 이상']
    analysis_df['SALARY_BIN'] = pd.cut(analysis_df['ANNUAL_SALARY'], bins=salary_bins, labels=salary_labels, right=False)

    # 8. 최종 정리 및 반환
    # 필요한 컬럼만 선택하여 메모리 관리
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
    # --- 글로벌 필터 값들을 인자로 받음 ---
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
    글로벌 필터가 적용된 월별 직원 상태 데이터를 기반으로,
    basic_proposal(인원 변동 현황)에 필요한 모든 차원의 데이터를 집계하여 반환합니다.
    """
    # 1. 모든 직원의 '월별 상태' 마스터 테이블을 불러옵니다. (캐싱됨)
    monthly_state_df = _get_monthly_employee_state_df()

    # 2. 전달받은 글로벌 필터 값으로 데이터 사전 필터링
    filtered_df = monthly_state_df.copy()
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

    # 3. 필터링된 데이터를 기반으로 모든 차원에 대해 데이터 집계
    data_bundle = {}
    
    # 분석할 차원 목록 (한글 UI 이름과 데이터프레임 컬럼명 매핑)
    dimensions = {
        '부서별': 'DIVISION_NAME', '직무별': 'JOB_L1_NAME', '직위직급별': 'POSITION_NAME',
        '성별': 'GENDER', '연령별': 'AGE_BIN', '경력연차별': 'CAREER_BIN',
        '연봉구간별': 'SALARY_BIN', '지역별': 'REGION_CATEGORY', '계약별': 'CONT_CATEGORY'
    }

    # '전체' 및 각 차원에 대해 루프를 돌며 집계
    all_dims_to_process = {'전체': None, **{ui_name: col_name for ui_name, col_name in dimensions.items()}}

    for ui_name, col_name in all_dims_to_process.items():
        grouping_cols = ['PERIOD_DT']
        if col_name:
            grouping_cols.append(col_name)
        
        # 필터링된 데이터에 해당 컬럼이 없으면 건너뜀
        if col_name and col_name not in filtered_df.columns:
            continue

        # 총원 집계
        headcount_df = filtered_df.groupby(grouping_cols, observed=False).size().reset_index(name='HEADCOUNT')
        if headcount_df.empty: # 해당 필터 조합에 데이터가 없으면 빈 결과를 저장하고 다음으로
            data_bundle[ui_name] = {'monthly': pd.DataFrame(), 'quarterly': pd.DataFrame()}
            continue

        # 입사자/퇴사자 집계
        hires_df = filtered_df[filtered_df['IN_DATE'].dt.to_period('M') == filtered_df['PERIOD_DT'].dt.to_period('M')]
        leavers_df = filtered_df[filtered_df['OUT_DATE'].dt.to_period('M') == filtered_df['PERIOD_DT'].dt.to_period('M')]
        
        hires_summary = hires_df.groupby(grouping_cols, observed=False).size().reset_index(name='NEW_HIRES')
        leavers_summary = leavers_df.groupby(grouping_cols, observed=False).size().reset_index(name='LEAVERS')
        
        # 월별 데이터 병합
        monthly_summary = pd.merge(headcount_df, hires_summary, on=grouping_cols, how='left')
        monthly_summary = pd.merge(monthly_summary, leavers_summary, on=grouping_cols, how='left')
        monthly_summary[['NEW_HIRES', 'LEAVERS']] = monthly_summary[['NEW_HIRES', 'LEAVERS']].fillna(0).astype(int)
        
        # 분기별 데이터 생성
        monthly_summary['QUARTER'] = monthly_summary['PERIOD_DT'].dt.to_period('Q')
        quarterly_summary = monthly_summary.groupby(['QUARTER'] + ([col_name] if col_name else []), observed=False).agg(
            NEW_HIRES=('NEW_HIRES', 'sum'),
            LEAVERS=('LEAVERS', 'sum'),
            HEADCOUNT=('HEADCOUNT', 'last')
        ).reset_index()
        
        data_bundle[ui_name] = {
            'monthly': monthly_summary,
            'quarterly': quarterly_summary,
        }
            
    return data_bundle

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
    글로벌 필터를 적용하여 분석 대상을 선정한 뒤, 승진 소요 기간을 계산합니다.
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
    emp_details = emp_df[['EMP_ID', 'IN_DATE', 'OUT_DATE', 'GENDER', 'PERSONAL_ID', 'DURATION']].copy()
    
    # 2-1. 정적/계산 속성 추가
    emp_details['GENDER'] = emp_details['GENDER'].map({'M': '남성', 'F': '여성'})
    emp_details['AGE'] = emp_details['PERSONAL_ID'].apply(calculate_age)
    emp_details['TENURE_YEARS'] = emp_details['DURATION'] / 365.25
    
    # 2-2. 첫 소속/직무/직위 정보 (필터 기준)
    first_dept = department_info_df.sort_values('DEP_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_job = job_info_df.sort_values('JOB_APP_START_DATE').groupby('EMP_ID').first().reset_index()
    first_pos = position_info_df.sort_values('GRADE_START_DATE').groupby('EMP_ID').first().reset_index()

    # 2-3. 최신 계약/지역/연봉 정보 (필터 기준)
    last_contract = contract_info_df.sort_values('CONT_START_DATE').groupby('EMP_ID').last().reset_index()
    last_region = region_info_df.sort_values('REG_APP_START_DATE').groupby('EMP_ID').last().reset_index()
    last_salary = salary_contract_info_df.sort_values('SAL_START_DATE').groupby('EMP_ID').last().reset_index()
    
    # 2-4. 과거 총 경력 계산
    prior_career_summary = career_info_df.groupby('EMP_ID')['CAREER_DURATION'].sum() / 365.25
    
    # 2-5. 헬퍼 데이터 및 이름 정보 매핑
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
    last_region['REGION_CATEGORY'] = '해외 현장'
    last_region.loc[last_region['DOMESTIC_YN'] == 'Y', 'REGION_CATEGORY'] = '국내 현장'
    last_region.loc[last_region['REG_NAME'] == '서울특별시', 'REGION_CATEGORY'] = '서울 본사'

    # 2-6. 모든 필터 기준 정보 병합
    emp_details = pd.merge(emp_details, first_dept[['EMP_ID', 'DIVISION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_job[['EMP_ID', 'JOB_L1_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, first_pos[['EMP_ID', 'POSITION_NAME']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_contract[['EMP_ID', 'CONT_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_region[['EMP_ID', 'REGION_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, last_salary[['EMP_ID', 'SAL_AMOUNT', 'PAY_CATEGORY']], on='EMP_ID', how='left')
    emp_details = pd.merge(emp_details, prior_career_summary.rename('TOTAL_PRIOR_CAREER_YEARS'), on='EMP_ID', how='left')
    
    # 2-7. 필터링을 위한 그룹(Bin) 정보 추가
    emp_details['TOTAL_PRIOR_CAREER_YEARS'] = emp_details['TOTAL_PRIOR_CAREER_YEARS'].fillna(0)
    emp_details['TOTAL_CAREER_YEARS'] = emp_details['TENURE_YEARS'] + emp_details['TOTAL_PRIOR_CAREER_YEARS']
    
    age_bins = [-1, 19, 29, 39, 49, 150]; age_labels = ['20세 미만', '20-29세', '30-39세', '40-49세', '50세 이상']
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    
    career_bins = [-1, 1, 3, 7, 15, 150]; career_labels = ['1년 미만', '1~3년', '3~7년', '7~15년', '15년 이상']
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] # 연봉 환산 로직
    emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    emp_details.loc[emp_details['PAY_CATEGORY'] == '주급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 52
    emp_details.loc[emp_details['PAY_CATEGORY'] == '일급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 250
    emp_details.loc[emp_details['PAY_CATEGORY'] == '시급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 2080
    salary_bins = [-1, 39999999, 59999999, 79999999, 99999999, float('inf')]; salary_labels = ['4,000만원 미만', '4,000~5,999만원', '6,000~7,999만원', '8,000~9,999만원', '1억원 이상']
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
        return {"analysis_df": pd.DataFrame(), "aggregate_df_div": pd.DataFrame(), "aggregate_df_job": pd.DataFrame()}

    # 4. 필터링된 직원들만을 대상으로 승진 소요 기간 계산
    pos_info = pd.merge(position_info_df, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID')
    pos_info_filtered = pos_info[pos_info['EMP_ID'].isin(filtered_emp_ids)]
    
    position_start_dates = pos_info_filtered.groupby(['EMP_ID', 'POSITION_NAME'])['GRADE_START_DATE'].min().unstack()

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
        "analysis_df": analysis_df
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
    division_order = base_data["department_table"].division_order

    # 2. 글로벌 필터링을 위한 마스터 직원 테이블 생성 (prepare_proposal_01_data와 동일)
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
    
    age_bins = [-1, 19, 29, 39, 49, 150]; age_labels = ['20세 미만', '20-29세', '30-39세', '40-49세', '50세 이상']
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    career_bins = [-1, 1, 3, 7, 15, 150]; career_labels = ['1년 미만', '1~3년', '3~7년', '7~15년', '15년 이상']
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    salary_bins = [-1, 39999999, 59999999, 79999999, 99999999, float('inf')]; salary_labels = ['4,000만원 미만', '4,000~5,999만원', '6,000~7,999만원', '8,000~9,999만원', '1억원 이상']
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
    글로벌 필터를 적용하여 분석 대상을 선정한 뒤, 연령 분포 데이터를 생성합니다.
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

    if filtered_df.empty:
        return {"analysis_df": pd.DataFrame(), "aggregate_df_div": pd.DataFrame(), "aggregate_df_job": pd.DataFrame()}

    # 4. 최종 데이터 묶음 반환
    return {
        "analysis_df": filtered_df
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
    글로벌 필터를 적용하여, 분석에 필요한 상세 데이터프레임을 생성합니다.
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

    # 3. 이 분석(Proposal 04)에만 필요한 추가 가공
    # 그래프 X축(1년 단위)을 위한 근속년수 그룹핑
    if not filtered_df.empty:
        max_tenure = int(filtered_df['TENURE_YEARS'].max())
        bins = range(0, max_tenure + 2)
        labels = range(0, max_tenure + 1)
        filtered_df['TENURE_BIN'] = pd.cut(filtered_df['TENURE_YEARS'], bins=bins, right=False, labels=labels)
    else:
        # 데이터가 없을 경우 빈 컬럼 추가
        filtered_df['TENURE_BIN'] = pd.Series(dtype='int')

    # 4. 최종 analysis_df 반환
    # 이 데이터프레임은 view 모듈에서 그래프를 그리고, app.py에서 피벗 테이블을 만드는 데 사용됩니다.
    return {"analysis_df": filtered_df}

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
    글로벌 필터를 적용하여 분석 대상을 선정한 뒤, 모든 차원의 연간 퇴사율 데이터를 생성합니다.
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

    # 2. 글로벌 필터링을 위한 마스터 직원 테이블 생성 (prepare_proposal_01_data와 동일)
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
    
    age_bins = [-1, 19, 29, 39, 49, 150]; age_labels = ['20세 미만', '20-29세', '30-39세', '40-49세', '50세 이상']
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    career_bins = [-1, 1, 3, 7, 15, 150]; career_labels = ['1년 미만', '1~3년', '3~7년', '7~15년', '15년 이상']
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    salary_bins = [-1, 39999999, 59999999, 79999999, 99999999, float('inf')]; salary_labels = ['4,000만원 미만', '4,000~5,999만원', '6,000~7,999만원', '8,000~9,999만원', '1억원 이상']
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
        return {"analysis_df": pd.DataFrame(), "overall_turnover_df": pd.DataFrame()}

    # 4. 필터링된 직원 대상 연간 퇴사율 계산
    leaver_years = emp_df.dropna(subset=['OUT_DATE'])['OUT_DATE'].dt.year.unique()
    analysis_years = sorted([y for y in leaver_years if y < datetime.datetime.now().year])
    
    turnover_records = []
    overall_turnover_records = []

    pos_info_with_name = pd.merge(position_info_df, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID')
    pos_info_sorted = pos_info_with_name.sort_values('GRADE_START_DATE')

    for year in analysis_years:
        year_start, year_end = pd.to_datetime(f'{year}-01-01'), pd.to_datetime(f'{year}-12-31')
        
        leavers_in_year = emp_df[(emp_df['OUT_DATE'] >= year_start) & (emp_df['OUT_DATE'] <= year_end) & (emp_df['EMP_ID'].isin(filtered_emp_ids))]
        active_in_year = emp_df[(emp_df['IN_DATE'] <= year_end) & (emp_df['OUT_DATE'].isnull() | (emp_df['OUT_DATE'] >= year_start)) & (emp_df['EMP_ID'].isin(filtered_emp_ids))]
        
        if active_in_year.empty: continue

        overall_rate = (len(leavers_in_year) / len(active_in_year)) * 100
        overall_turnover_records.append({'YEAR': year, 'TURNOVER_RATE': overall_rate})
            
        if leavers_in_year.empty: continue
            
        leavers_with_attrs = pd.merge_asof(leavers_in_year[['EMP_ID', 'OUT_DATE']].sort_values('OUT_DATE'), dept_info_sorted, left_on='OUT_DATE', right_on='DEP_APP_START_DATE', by='EMP_ID', direction='backward')
        leavers_with_attrs = pd.merge_asof(leavers_with_attrs.sort_values('OUT_DATE'), job_info_sorted, left_on='OUT_DATE', right_on='JOB_APP_START_DATE', by='EMP_ID', direction='backward')
        leavers_with_attrs = pd.merge_asof(leavers_with_attrs.sort_values('OUT_DATE'), pos_info_sorted, left_on='OUT_DATE', right_on='GRADE_START_DATE', by='EMP_ID', direction='backward')
        
        active_with_attrs = pd.merge_asof(active_in_year[['EMP_ID', 'IN_DATE']].sort_values('IN_DATE'), dept_info_sorted, left_on='IN_DATE', right_on='DEP_APP_START_DATE', by='EMP_ID', direction='backward')
        active_with_attrs = pd.merge_asof(active_with_attrs.sort_values('IN_DATE'), job_info_sorted, left_on='IN_DATE', right_on='JOB_APP_START_DATE', by='EMP_ID', direction='backward')
        active_with_attrs = pd.merge_asof(active_with_attrs.sort_values('IN_DATE'), pos_info_sorted, left_on='IN_DATE', right_on='GRADE_START_DATE', by='EMP_ID', direction='backward')

        for df in [leavers_with_attrs, active_with_attrs]:
            if not df.empty:
                parent_info = df['DEP_ID'].apply(lambda x: find_parents(x, dept_level_map, parent_map_dept, dept_name_map))
                df[['DIVISION_NAME', 'OFFICE_NAME']] = parent_info
                df['JOB_L1_NAME'] = df['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
                df['JOB_L2_NAME'] = df['JOB_ID'].apply(lambda x: job_name_map.get(get_level2_ancestor(x, job_df_indexed, parent_map_job)))

        dimensions = {
            'DIVISION': ['DIVISION_NAME'], 'OFFICE': ['DIVISION_NAME', 'OFFICE_NAME'],
            'JOB_L1': ['JOB_L1_NAME'], 'JOB_L2': ['JOB_L1_NAME', 'JOB_L2_NAME'],
            'POSITION': ['POSITION_NAME'], 'GRADE': ['POSITION_NAME', 'GRADE_ID'],
        }

        for dim_name, cols in dimensions.items():
            leavers_grouped = leavers_with_attrs.dropna(subset=cols).groupby(cols, observed=False).size()
            headcount_grouped = active_with_attrs.dropna(subset=cols).groupby(cols, observed=False).size()
            
            turnover_rates = (leavers_grouped / headcount_grouped * 100).fillna(0)

            for group_keys, rate in turnover_rates.items():
                record = {'YEAR': year, 'GROUP_TYPE': dim_name, 'TURNOVER_RATE': rate}
                keys = [group_keys] if isinstance(group_keys, str) else group_keys
                
                if 'NAME' in dim_name: record['GROUP_NAME'] = keys[-1]
                if dim_name == 'OFFICE': record['DIVISION_NAME'], record['GROUP_NAME'] = keys
                elif dim_name == 'JOB_L2': record['JOB_L1_NAME'], record['GROUP_NAME'] = keys
                elif dim_name == 'GRADE': record['POSITION_NAME'], record['GROUP_NAME'] = keys
                else: record['GROUP_NAME'] = keys[0]
                turnover_records.append(record)

    analysis_df = pd.DataFrame(turnover_records)
    overall_turnover_df = pd.DataFrame(overall_turnover_records)

    return {"analysis_df": analysis_df, "overall_turnover_df": overall_turnover_df}

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
    제안 6: 입사 연도별 잔존율 코호트 분석
    글로벌 필터를 적용하여 분석 대상을 선정한 뒤, 부서/직무/직위별 코호트 데이터를 생성합니다.
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
    division_order = base_data["department_table"].division_order
    job_l1_order = base_data["job_table"].job_l1_order
    position_order = base_data["position_table"].position_order

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
    
    age_bins = [-1, 19, 29, 39, 49, 150]; age_labels = ['20세 미만', '20-29세', '30-39세', '40-49세', '50세 이상']
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    career_bins = [-1, 1, 3, 7, 15, 150]; career_labels = ['1년 미만', '1~3년', '3~7년', '7~15년', '15년 이상']
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    salary_bins = [-1, 39999999, 59999999, 79999999, 99999999, float('inf')]; salary_labels = ['4,000만원 미만', '4,000~5,999만원', '6,000~7,999만원', '8,000~9,999만원', '1억원 이상']
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
        return {"부서별": {}, "직무별": {}, "직위직급별": {}}
        
    # 4. 필터링된 직원들만을 대상으로 코호트 분석 수행
    # 코호트 분석의 기반이 될 데이터프레임
    analysis_df = emp_df[emp_df['EMP_ID'].isin(filtered_emp_ids)][['EMP_ID', 'IN_DATE', 'OUT_DATE']].copy()
    
    # 분석에 필요한 차원 정보(첫 부서, 첫 직무, 첫 직위)를 analysis_df에 병합
    analysis_df = pd.merge(analysis_df, filtered_emps_df[['EMP_ID', 'DIVISION_NAME', 'JOB_L1_NAME', 'POSITION_NAME']], on='EMP_ID', how='left')
    
    # 5. 각 차원별로 코호트 데이터 계산
    data_bundle = {}
    
    # 부서별 코호트
    cohort_map_div = {}
    cohort_map_div['전체'] = _create_cohort_data(analysis_df)
    for div_name in division_order:
        df_filtered = analysis_df[analysis_df['DIVISION_NAME'] == div_name]
        cohort_map_div[div_name] = _create_cohort_data(df_filtered)
    data_bundle['부서별'] = cohort_map_div
    
    # 직무별 코호트
    cohort_map_job = {}
    cohort_map_job['전체'] = _create_cohort_data(analysis_df)
    for job_name in job_l1_order:
        df_filtered = analysis_df[analysis_df['JOB_L1_NAME'] == job_name]
        cohort_map_job[job_name] = _create_cohort_data(df_filtered)
    data_bundle['직무별'] = cohort_map_job

    # 직위직급별 코호트
    cohort_map_pos = {}
    cohort_map_pos['전체'] = _create_cohort_data(analysis_df)
    for pos_name in position_order:
        df_filtered = analysis_df[analysis_df['POSITION_NAME'] == pos_name]
        cohort_map_pos[pos_name] = _create_cohort_data(df_filtered)
    data_bundle['직위직급별'] = cohort_map_pos
    
    return data_bundle

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
    career_info_df = base_data["career_info_df"]
    department_info_df = base_data["department_info_df"]
    job_info_df = base_data["job_info_df"]
    position_info_df = base_data["position_info_df"]
    salary_contract_info_df = base_data["salary_contract_info_df"]
    region_info_df = base_data["region_info_df"]
    contract_info_df = base_data["contract_info_df"]
    department_df = base_data["department_df"]
    job_df = base_data["job_df"]
    position_df = base_data["position_df"]
    region_df = base_data["region_df"]

    # 2. 글로벌 필터링을 위한 마스터 직원 테이블 생성 (prepare_proposal_01_data와 동일)
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
    
    age_bins = [-1, 19, 29, 39, 49, 150]; age_labels = ['20세 미만', '20-29세', '30-39세', '40-49세', '50세 이상']
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    career_bins = [-1, 1, 3, 7, 15, 150]; career_labels = ['1년 미만', '1~3년', '3~7년', '7~15년', '15년 이상']
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    salary_bins = [-1, 39999999, 59999999, 79999999, 99999999, float('inf')]; salary_labels = ['4,000만원 미만', '4,000~5,999만원', '6,000~7,999만원', '8,000~9,999만원', '1억원 이상']
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

    # 4. 필터링된 직원들만을 대상으로 재직기간 분석 데이터 생성
    # 경력 유형 계산
    career_summary = career_info_df[career_info_df['EMP_ID'].isin(filtered_emp_ids)].groupby('EMP_ID')['CAREER_REL_YN'].apply(
        lambda x: '관련 경력' if 'Y' in x.values else '비관련 경력'
    ).reset_index().rename(columns={'CAREER_REL_YN': 'CAREER_TYPE'})
    
    # 분석의 기반이 될 데이터프레임 생성
    analysis_df = emp_df[emp_df['EMP_ID'].isin(filtered_emp_ids)][['EMP_ID', 'DURATION']].copy()
    analysis_df = pd.merge(analysis_df, career_summary, on='EMP_ID', how='left')
    analysis_df['CAREER_TYPE'] = analysis_df['CAREER_TYPE'].fillna('경력 없음')
    analysis_df['TENURE_YEARS'] = analysis_df['DURATION'] / 365.25

    # 첫 직무 및 첫 부서 정보 병합
    analysis_df = pd.merge(analysis_df, first_job[['EMP_ID', 'JOB_L1_NAME']].rename(columns={'JOB_L1_NAME': 'JOB_CATEGORY'}), on='EMP_ID', how='left')
    analysis_df = pd.merge(analysis_df, first_dept[['EMP_ID', 'DIVISION_NAME']], on='EMP_ID', how='left')
    analysis_df = pd.merge(analysis_df, first_pos[['EMP_ID', 'POSITION_NAME']], on='EMP_ID', how='left')
    
    analysis_df = analysis_df.dropna(subset=['DIVISION_NAME', 'JOB_CATEGORY', 'POSITION_NAME'])

    return {"analysis_df": analysis_df}

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
    제안 8: 직무별 인력 유지 현황 분석 (재직자 vs 퇴사자)
    글로벌 필터를 적용하여 분석 대상을 선정한 뒤, 재직/퇴사자별 평균 근속년수 분석 데이터를 생성합니다.
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
    emp_details = emp_df[['EMP_ID', 'GENDER', 'PERSONAL_ID', 'DURATION', 'IN_DATE', 'OUT_DATE', 'CURRENT_EMP_YN']].copy()
    emp_details['GENDER'] = emp_details['GENDER'].map({'M': '남성', 'F': '여성'})
    emp_details['AGE'] = emp_details['PERSONAL_ID'].apply(calculate_age)
    emp_details['TENURE_YEARS'] = emp_details['DURATION'] / 365.25
    
    # 이 분석은 '마지막' 상태 기준이므로 last_ 사용, 필터 기준은 first_ 사용
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
    
    age_bins = [-1, 19, 29, 39, 49, 150]; age_labels = ['20세 미만', '20-29세', '30-39세', '40-49세', '50세 이상']
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    career_bins = [-1, 1, 3, 7, 15, 150]; career_labels = ['1년 미만', '1~3년', '3~7년', '7~15년', '15년 이상']
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    salary_bins = [-1, 39999999, 59999999, 79999999, 99999999, float('inf')]; salary_labels = ['4,000만원 미만', '4,000~5,999만원', '6,000~7,999만원', '8,000~9,999만원', '1억원 이상']
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

    # 4. 필터링된 직원들만을 대상으로 인력 유지 현황 분석 데이터 생성
    analysis_df = emp_details[emp_details['EMP_ID'].isin(filtered_emp_ids)][['EMP_ID', 'CURRENT_EMP_YN', 'TENURE_YEARS']].copy()
    
    # 모든 직원의 마지막 직무 및 부서 정보 가져오기
    last_job = job_info_df.sort_values('JOB_APP_START_DATE').groupby('EMP_ID').last()
    last_dept = department_info_df.sort_values('DEP_APP_START_DATE').groupby('EMP_ID').last()
    
    last_job['JOB_CATEGORY'] = last_job['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    last_dept['DIVISION_NAME'] = last_dept['DEP_ID'].apply(lambda x: find_division_name_for_dept(x, dept_level_map, parent_map_dept, dept_name_map))

    analysis_df = pd.merge(analysis_df, last_job[['JOB_CATEGORY']], on='EMP_ID', how='left')
    analysis_df = pd.merge(analysis_df, last_dept[['DIVISION_NAME']], on='EMP_ID', how='left')
    
    # 입사 시점 직위 정보 추가
    analysis_df = pd.merge(analysis_df, first_pos[['EMP_ID', 'POSITION_NAME']], on='EMP_ID', how='left')
    
    analysis_df['STATUS'] = np.where(analysis_df['CURRENT_EMP_YN'] == 'Y', '재직자', '퇴사자')
    analysis_df = analysis_df.dropna(subset=['JOB_CATEGORY', 'DIVISION_NAME', 'POSITION_NAME'])

    return {"analysis_df": analysis_df}

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
    제안 9: 조직 활력도 진단 (연간 직무 이동률)
    글로벌 필터를 적용하여 분석 대상을 선정한 뒤, 모든 차원의 연간 직무 이동률 데이터를 생성합니다.
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
    # (이전 함수들과 동일한 로직을 사용하여 emp_details 생성)
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
    
    age_bins = [-1, 19, 29, 39, 49, 150]; age_labels = ['20세 미만', '20-29세', '30-39세', '40-49세', '50세 이상']
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    career_bins = [-1, 1, 3, 7, 15, 150]; career_labels = ['1년 미만', '1~3년', '3~7년', '7~15년', '15년 이상']
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    salary_bins = [-1, 39999999, 59999999, 79999999, 99999999, float('inf')]; salary_labels = ['4,000만원 미만', '4,000~5,999만원', '6,000~7,999만원', '8,000~9,999만원', '1억원 이상']
    emp_details['SALARY_BIN'] = pd.cut(emp_details['ANNUAL_SALARY'], bins=salary_bins, labels=salary_labels, right=False)

    # 3. 글로벌 필터 적용
    filtered_emps_df = emp_details.copy()
    # ... (9개 필터 if 문 전체 블록) ...
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
        return {"analysis_df": pd.DataFrame(), "overall_df": pd.DataFrame()}

    # 4. 필터링된 직원 대상 연간 직무 이동률 계산
    job_changes = job_info_df[job_info_df['EMP_ID'].isin(filtered_emp_ids)].copy()
    job_changes = pd.merge(job_changes, emp_df[['EMP_ID', 'IN_DATE']], on='EMP_ID', how='left')
    job_changes = job_changes[job_changes['JOB_APP_START_DATE'] > job_changes['IN_DATE']] # 첫 직무 제외
    job_changes['YEAR'] = job_changes['JOB_APP_START_DATE'].dt.year

    analysis_records = []
    overall_records = []
    all_years = sorted(job_changes['YEAR'].unique())
    
    pos_info_with_name = pd.merge(position_info_df, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID')
    pos_info_sorted = pos_info_with_name.sort_values('GRADE_START_DATE')
    dept_info_sorted = department_info_df.sort_values('DEP_APP_START_DATE')

    for year in all_years:
        year_end = pd.to_datetime(f'{year}-12-31')
        active_in_year = emp_df[(emp_df['IN_DATE'] <= year_end) & (emp_df['OUT_DATE'].isnull() | (emp_df['OUT_DATE'] > year_end)) & (emp_df['EMP_ID'].isin(filtered_emp_ids))].copy()
        changes_in_year = job_changes[job_changes['YEAR'] == year].copy()
        
        if active_in_year.empty: continue

        overall_rate = (changes_in_year['EMP_ID'].nunique() / active_in_year['EMP_ID'].nunique()) * 100
        overall_records.append({'YEAR': year, 'MOBILITY_RATE': overall_rate})
            
        # 재직자(분모)와 이동자(분자)의 연말 기준 속성 부여
        active_in_year['DATE_SNAPSHOT'] = year_end
        active_with_attrs = pd.merge_asof(active_in_year.sort_values('DATE_SNAPSHOT'), dept_info_sorted, left_on='DATE_SNAPSHOT', right_on='DEP_APP_START_DATE', by='EMP_ID')
        active_with_attrs = pd.merge_asof(active_with_attrs.sort_values('DATE_SNAPSHOT'), pos_info_sorted, left_on='DATE_SNAPSHOT', right_on='GRADE_START_DATE', by='EMP_ID')
        
        changes_in_year['DATE_SNAPSHOT'] = changes_in_year['JOB_APP_START_DATE']
        changes_with_attrs = pd.merge_asof(changes_in_year.sort_values('DATE_SNAPSHOT'), dept_info_sorted, left_on='DATE_SNAPSHOT', right_on='DEP_APP_START_DATE', by='EMP_ID')
        changes_with_attrs = pd.merge_asof(changes_with_attrs.sort_values('DATE_SNAPSHOT'), pos_info_sorted, left_on='DATE_SNAPSHOT', right_on='GRADE_START_DATE', by='EMP_ID')
        
        for df in [active_with_attrs, changes_with_attrs]:
            parent_info = df['DEP_ID'].apply(lambda x: find_parents(x, dept_level_map, parent_map_dept, dept_name_map))
            df[['DIVISION_NAME', 'OFFICE_NAME']] = parent_info

        # 각 차원별 이동률 계산
        dimensions = {
            'DIVISION': ['DIVISION_NAME'], 'OFFICE': ['DIVISION_NAME', 'OFFICE_NAME'],
            'POSITION': ['POSITION_NAME'], 'GRADE': ['POSITION_NAME', 'GRADE_ID']
        }

        for dim_name, cols in dimensions.items():
            headcount_grouped = active_with_attrs.dropna(subset=cols).groupby(cols, observed=False)['EMP_ID'].nunique()
            changes_grouped = changes_with_attrs.dropna(subset=cols).groupby(cols, observed=False)['EMP_ID'].nunique()
            mobility_rates = (changes_grouped / headcount_grouped * 100).fillna(0)

            for group_keys, rate in mobility_rates.items():
                record = {'YEAR': year, 'GROUP_TYPE': dim_name, 'MOBILITY_RATE': rate}
                keys = [group_keys] if isinstance(group_keys, str) else group_keys
                if dim_name == 'OFFICE': record['DIVISION_NAME'], record['GROUP_NAME'] = keys
                elif dim_name == 'GRADE': record['POSITION_NAME'], record['GROUP_NAME'] = keys
                else: record['GROUP_NAME'] = keys[0]
                analysis_records.append(record)
    
    analysis_df = pd.DataFrame(analysis_records)
    overall_df = pd.DataFrame(overall_records)

    return {"analysis_df": analysis_df, "overall_df": overall_df}

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
    제안 10: 학력/경력과 초봉의 관계 분석
    글로벌 필터를 적용하여 분석 대상을 선정한 뒤, 초봉 분석 데이터를 생성합니다.
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
    
    age_bins = [-1, 19, 29, 39, 49, 150]; age_labels = ['20세 미만', '20-29세', '30-39세', '40-49세', '50세 이상']
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    career_bins = [-1, 1, 3, 7, 15, 150]; career_labels = ['1년 미만', '1~3년', '3~7년', '7~15년', '15년 이상']
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    salary_bins = [-1, 39999999, 59999999, 79999999, 99999999, float('inf')]; salary_labels = ['4,000만원 미만', '4,000~5,999만원', '6,000~7,999만원', '8,000~9,999만원', '1억원 이상']
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

    # 4. 필터링된 직원 대상 초봉 분석 데이터 생성
    # 초봉 정보
    initial_contracts = salary_contract_info_df[
        (salary_contract_info_df['PAY_CATEGORY'] == '연봉') &
        (salary_contract_info_df['EMP_ID'].isin(filtered_emp_ids))
    ].sort_values('SAL_START_DATE').groupby('EMP_ID').first().reset_index()
    initial_contracts = initial_contracts[['EMP_ID', 'SAL_AMOUNT']].rename(columns={'SAL_AMOUNT': 'INITIAL_SALARY'})

    # 최종 학력 정보
    school_history = school_info_df[school_info_df['EMP_ID'].isin(filtered_emp_ids)].copy()
    school_history = pd.merge(school_history, school_df, on='SCHOOL_ID', how='left')
    final_education = school_history.sort_values('GRAD_YEAR').groupby('EMP_ID').last().reset_index()
    final_education = final_education[['EMP_ID', 'SCHOOL_LEVEL', 'MAJOR_CATEGORY']]

    # 과거 총 경력 정보
    prior_career = career_info_df[career_info_df['EMP_ID'].isin(filtered_emp_ids)].copy()
    prior_career_summary = prior_career.groupby('EMP_ID')['CAREER_DURATION'].sum().reset_index()
    prior_career_summary['TOTAL_PRIOR_CAREER_YEARS'] = prior_career_summary['CAREER_DURATION'] / 365.25

    # 최종 분석 데이터프레임 병합
    analysis_df = pd.merge(initial_contracts, final_education, on='EMP_ID', how='inner')
    analysis_df = pd.merge(analysis_df, prior_career_summary[['EMP_ID', 'TOTAL_PRIOR_CAREER_YEARS']], on='EMP_ID', how='left')
    analysis_df['TOTAL_PRIOR_CAREER_YEARS'] = analysis_df['TOTAL_PRIOR_CAREER_YEARS'].fillna(0)
    analysis_df = analysis_df.dropna(subset=['INITIAL_SALARY', 'SCHOOL_LEVEL', 'MAJOR_CATEGORY'])

    # 경력 그룹(Bin) 정보 추가
    bins = [-1, 3, 7, 100]
    labels = ['신입 (0~3년)', '주니어 (3~7년)', '시니어 (7년+)']
    analysis_df['CAREER_BIN'] = pd.cut(analysis_df['TOTAL_PRIOR_CAREER_YEARS'], bins=bins, labels=labels, right=True)

    return {"analysis_df": analysis_df}

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
    글로벌 필터를 적용하여 분석 대상을 선정한 뒤, 초과근무 분포 분석 데이터를 생성합니다.
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
    
    age_bins = [-1, 19, 29, 39, 49, 150]; age_labels = ['20세 미만', '20-29세', '30-39세', '40-49세', '50세 이상']
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    career_bins = [-1, 1, 3, 7, 15, 150]; career_labels = ['1년 미만', '1~3년', '3~7년', '7~15년', '15년 이상']
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    salary_bins = [-1, 39999999, 59999999, 79999999, 99999999, float('inf')]; salary_labels = ['4,000만원 미만', '4,000~5,999만원', '6,000~7,999만원', '8,000~9,999만원', '1억원 이상']
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

    # 4. 필터링된 직원들의 일별 초과근무 데이터에 시점별 부서 정보 부여
    daily_work_df = daily_work_info_df[daily_work_info_df['EMP_ID'].isin(filtered_emp_ids)].copy()
    
    # 이 분석은 시점별로 변하는 '부서'가 중요하므로, daily_work_df에 직접 merge_asof 수행
    dept_info_sorted = department_info_df.sort_values(['DEP_APP_START_DATE', 'EMP_ID'])
    analysis_df = pd.merge_asof(
        daily_work_df.sort_values('DATE'),
        dept_info_sorted[['EMP_ID', 'DEP_APP_START_DATE', 'DEP_ID']],
        left_on='DATE', right_on='DEP_APP_START_DATE', by='EMP_ID', direction='backward'
    )
    
    parent_info = analysis_df['DEP_ID'].apply(lambda x: find_parents(x, dept_level_map, parent_map_dept, dept_name_map))
    analysis_df = pd.concat([analysis_df, parent_info], axis=1)
    analysis_df['OFFICE_NAME'] = analysis_df['OFFICE_NAME'].fillna('(Division 직속)')
    analysis_df = analysis_df.dropna(subset=['DIVISION_NAME', 'OFFICE_NAME'])

    return {"analysis_df": analysis_df}

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
    # (이전 함수들과 동일한 로직을 사용하여 emp_details 생성)
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
    
    age_bins = [-1, 19, 29, 39, 49, 150]; age_labels = ['20세 미만', '20-29세', '30-39세', '40-49세', '50세 이상']
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    career_bins = [-1, 1, 3, 7, 15, 150]; career_labels = ['1년 미만', '1~3년', '3~7년', '7~15년', '15년 이상']
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    salary_bins = [-1, 39999999, 59999999, 79999999, 99999999, float('inf')]; salary_labels = ['4,000만원 미만', '4,000~5,999만원', '6,000~7,999만원', '8,000~9,999만원', '1억원 이상']
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

    # 4. 필터링된 직원들의 일별 출근 데이터 준비
    # 4-1. 분석 대상 직원 선정 (일반 근무자 + 필터링된 직원) 및 샘플링
    normal_work_emp_ids = work_info_df[work_info_df['WORK_SYS_ID'] == 'WS001']['EMP_ID'].unique()
    target_emp_ids = np.intersect1d(normal_work_emp_ids, filtered_emp_ids)
    
    if len(target_emp_ids) > 0:
        num_to_sample = int(len(target_emp_ids) * 0.3) if len(target_emp_ids) > 10 else len(target_emp_ids) # 샘플링 수가 너무 적어지는 것 방지
        np.random.seed(42)
        sampled_emp_ids = np.random.choice(target_emp_ids, size=num_to_sample, replace=False)
    else:
        return {"analysis_df": pd.DataFrame()}

    work_records = detailed_work_info_df[
        (detailed_work_info_df['EMP_ID'].isin(sampled_emp_ids)) &
        (~detailed_work_info_df['WORK_ETC'].isin(['휴가', '주말 휴무', '비번', '휴무'])) &
        (detailed_work_info_df['DATE_START_TIME'] != '-')
    ].copy()

    # 4-2. 시점별 부서 및 직위 정보 추가
    work_records['DATE'] = pd.to_datetime(work_records['DATE'])
    dept_info_sorted = department_info_df.sort_values(['DEP_APP_START_DATE', 'EMP_ID'])
    pos_info_sorted = position_info_df.sort_values(['GRADE_START_DATE', 'EMP_ID'])
    analysis_df = work_records.sort_values(['DATE', 'EMP_ID'])

    analysis_df = pd.merge_asof(analysis_df, dept_info_sorted[['EMP_ID', 'DEP_APP_START_DATE', 'DEP_ID']], left_on='DATE', right_on='DEP_APP_START_DATE', by='EMP_ID', direction='backward')
    analysis_df = pd.merge_asof(analysis_df, pos_info_sorted[['EMP_ID', 'GRADE_START_DATE', 'POSITION_ID']], left_on='DATE', right_on='GRADE_START_DATE', by='EMP_ID', direction='backward')
    
    parent_info = analysis_df['DEP_ID'].apply(lambda x: find_parents(x, dept_level_map, parent_map_dept, dept_name_map))
    analysis_df = pd.concat([analysis_df, parent_info], axis=1)
    analysis_df = pd.merge(analysis_df, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID', how='left')
    analysis_df = analysis_df.dropna(subset=['DIVISION_NAME', 'OFFICE_NAME', 'POSITION_NAME'])

    # 4-3. 출근 시간(float) 계산
    analysis_df['START_HOUR'] = pd.to_datetime(analysis_df['DATE_START_TIME'], format='%H:%M', errors='coerce').dt.hour + \
                                pd.to_datetime(analysis_df['DATE_START_TIME'], format='%H:%M', errors='coerce').dt.minute / 60
    analysis_df = analysis_df.dropna(subset=['START_HOUR'])

    return {"analysis_df": analysis_df}

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
    글로벌 필터를 적용하여 분석 대상을 선정한 뒤, 초과근무 시간 분석 데이터를 생성합니다.
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
    
    age_bins = [-1, 19, 29, 39, 49, 150]; age_labels = ['20세 미만', '20-29세', '30-39세', '40-49세', '50세 이상']
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    career_bins = [-1, 1, 3, 7, 15, 150]; career_labels = ['1년 미만', '1~3년', '3~7년', '7~15년', '15년 이상']
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    salary_bins = [-1, 39999999, 59999999, 79999999, 99999999, float('inf')]; salary_labels = ['4,000만원 미만', '4,000~5,999만원', '6,000~7,999만원', '8,000~9,999만원', '1억원 이상']
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

    # 4. 필터링된 직원들의 일별 초과근무 데이터에 시점별 속성 정보 부여
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

    analysis_df = analysis_df.dropna(subset=['DIVISION_NAME', 'OFFICE_NAME', 'JOB_L1_NAME', 'JOB_L2_NAME', 'POSITION_NAME', 'GRADE_ID'])
    
    return {"analysis_df": analysis_df}

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
    
    age_bins = [-1, 19, 29, 39, 49, 150]; age_labels = ['20세 미만', '20-29세', '30-39세', '40-49세', '50세 이상']
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    career_bins = [-1, 1, 3, 7, 15, 150]; career_labels = ['1년 미만', '1~3년', '3~7년', '7~15년', '15년 이상']
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    salary_bins = [-1, 39999999, 59999999, 79999999, 99999999, float('inf')]; salary_labels = ['4,000만원 미만', '4,000~5,999만원', '6,000~7,999만원', '8,000~9,999만원', '1억원 이상']
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

    # 4. 필터링된 직원들의 일별 지각 데이터 준비
    work_records = detailed_work_info_df.copy()
    work_records = work_records[~work_records['WORK_ETC'].isin(['휴가', '주말 휴무', '비번', '휴무'])]
    work_records = work_records[work_records['DATE_START_TIME'] != '-']
    normal_work_emp_ids = work_info_df[work_info_df['WORK_SYS_ID'] == 'WS001']['EMP_ID'].unique()
    
    target_emp_ids = np.intersect1d(normal_work_emp_ids, filtered_emp_ids)
    work_records = work_records[work_records['EMP_ID'].isin(target_emp_ids)].copy()

    if work_records.empty:
        return {"analysis_df": pd.DataFrame()}
    
    work_records['DATE'] = pd.to_datetime(work_records['DATE'])
    
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
    
    analysis_df = analysis_df.dropna(subset=['JOB_L1_NAME', 'JOB_L2_NAME', 'POSITION_NAME', 'DIVISION_NAME', 'OFFICE_NAME'])
    
    # 5. '지각' 여부 판단
    analysis_df['START_TIME_OBJ'] = pd.to_datetime(analysis_df['DATE_START_TIME'], format='%H:%M', errors='coerce').dt.time
    gso_mask = analysis_df['OFFICE_NAME'] == 'Global Sales Office'
    analysis_df['IS_LATE'] = False # 기본값을 False로 설정
    
    # NaN이 아닌 행에 대해서만 조건부 할당
    not_na_mask = analysis_df['START_TIME_OBJ'].notna()
    analysis_df.loc[gso_mask & not_na_mask, 'IS_LATE'] = analysis_df.loc[gso_mask & not_na_mask, 'START_TIME_OBJ'] > datetime.time(11, 0)
    analysis_df.loc[~gso_mask & not_na_mask, 'IS_LATE'] = analysis_df.loc[~gso_mask & not_na_mask, 'START_TIME_OBJ'] > datetime.time(10, 0)

    return {"analysis_df": analysis_df}

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
    
    age_bins = [-1, 19, 29, 39, 49, 150]; age_labels = ['20세 미만', '20-29세', '30-39세', '40-49세', '50세 이상']
    emp_details['AGE_BIN'] = pd.cut(emp_details['AGE'], bins=age_bins, labels=age_labels)
    career_bins = [-1, 1, 3, 7, 15, 150]; career_labels = ['1년 미만', '1~3년', '3~7년', '7~15년', '15년 이상']
    emp_details['CAREER_BIN'] = pd.cut(emp_details['TOTAL_CAREER_YEARS'], bins=career_bins, labels=career_labels, right=False)
    emp_details['ANNUAL_SALARY'] = emp_details['SAL_AMOUNT']; emp_details.loc[emp_details['PAY_CATEGORY'] == '월급', 'ANNUAL_SALARY'] = emp_details['SAL_AMOUNT'] * 12
    salary_bins = [-1, 39999999, 59999999, 79999999, 99999999, float('inf')]; salary_labels = ['4,000만원 미만', '4,000~5,999만원', '6,000~7,999만원', '8,000~9,999만원', '1억원 이상']
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

    # 4. 필터링된 직원들의 부서 이동 이벤트 식별
    dept_changes = department_info_df[department_info_df['EMP_ID'].isin(filtered_emp_ids)].sort_values(['EMP_ID', 'DEP_APP_START_DATE'])
    dept_changes['PREV_DEP_ID'] = dept_changes.groupby('EMP_ID')['DEP_ID'].shift(1)
    dept_changes = dept_changes[dept_changes['PREV_DEP_ID'].notna() & (dept_changes['DEP_ID'] != dept_changes['PREV_DEP_ID'])].copy()
    dept_changes = dept_changes.rename(columns={'DEP_APP_START_DATE': 'CHANGE_DATE'})

    if dept_changes.empty:
        return {"analysis_df": pd.DataFrame()}

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
        return {"analysis_df": pd.DataFrame()}

    # 6. 부서 평균(Baseline) 계산
    daily_work_with_dept = pd.merge_asof(daily_work_filtered_df.sort_values('DATE'), department_info_df.sort_values('DEP_APP_START_DATE'), left_on='DATE', right_on='DEP_APP_START_DATE', by='EMP_ID', direction='backward')
    parent_info_daily = daily_work_with_dept['DEP_ID'].apply(lambda x: find_parents(x, dept_level_map, parent_map_dept, dept_name_map))
    daily_work_with_dept = pd.concat([daily_work_with_dept, parent_info_daily], axis=1)
    daily_work_with_dept = daily_work_with_dept.dropna(subset=['DIVISION_NAME', 'OFFICE_NAME'])
    
    div_overall_avg = daily_work_with_dept.groupby('DIVISION_NAME', observed=False)['OVERTIME_MINUTES'].mean().reset_index().rename(columns={'OVERTIME_MINUTES': 'DEPT_AVG'})
    office_overall_avg = daily_work_with_dept.groupby(['DIVISION_NAME','OFFICE_NAME'], observed=False)['OVERTIME_MINUTES'].mean().reset_index().rename(columns={'OVERTIME_MINUTES': 'DEPT_AVG'})
    
    # 7. 최종 분석 데이터프레임 생성
    parent_info = analysis_df['NEW_DEP_ID'].apply(lambda x: find_parents(x, dept_level_map, parent_map_dept, dept_name_map))
    analysis_df = pd.concat([analysis_df, parent_info], axis=1)
    analysis_df = analysis_df.dropna(subset=['DIVISION_NAME', 'OFFICE_NAME'])
    
    # Division 레벨 데이터
    div_summary = analysis_df.groupby('DIVISION_NAME', observed=False)[['OT_BEFORE', 'OT_AFTER']].mean()
    div_summary = pd.merge(div_summary, div_overall_avg, on='DIVISION_NAME').reset_index()
    div_summary['GROUP_TYPE'] = 'Division'
    
    # Office 레벨 데이터
    office_summary = analysis_df.groupby(['DIVISION_NAME', 'OFFICE_NAME'], observed=False)[['OT_BEFORE', 'OT_AFTER']].mean()
    office_summary = pd.merge(office_summary, office_overall_avg, on=['DIVISION_NAME','OFFICE_NAME']).reset_index()
    office_summary['GROUP_TYPE'] = 'Office'

    # view에서 사용하기 편하도록 하나의 DataFrame으로 통합
    div_summary = div_summary.rename(columns={'DIVISION_NAME': 'GROUP_NAME'})
    office_summary = office_summary.rename(columns={'OFFICE_NAME': 'GROUP_NAME'})
    
    final_analysis_df = pd.concat([div_summary, office_summary], ignore_index=True)

    return {"analysis_df": final_analysis_df}

# 각 함수의 결과는 @st.cache_data로 캐싱되어야 합니다.