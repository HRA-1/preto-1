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

# --------------------------------------------------------------------------
# --- Proposal별 데이터 준비 함수 ---
# --------------------------------------------------------------------------

# 여기에 각 proposal에 필요한 데이터 준비 함수들을 추가합니다.
# 예시로 proposal 04 (근속년수 분포)와 proposal 05 (퇴사율) 데이터 준비 함수를 작성합니다.
# 나머지 proposal들도 이와 유사한 패턴으로 함수를 추가해나갈 수 있습니다.

@st.cache_data
def prepare_proposal_04_data():
    """
    Proposal 04 (조직 경험 자산 현황) 분석에 필요한 데이터를 사전 가공합니다.
    - 부서별, 직무별, 직위직급별 분석 데이터를 모두 포함합니다.
    """
    snapshot_df = _get_current_employee_snapshot()
    snapshot_df['TENURE_BIN'] = pd.cut(
        snapshot_df['TENURE_YEARS'], 
        bins=range(0, int(snapshot_df['TENURE_YEARS'].max()) + 2), 
        right=False, 
        labels=range(0, int(snapshot_df['TENURE_YEARS'].max()) + 1)
    )
    
    # 부서별 집계
    div_summary = snapshot_df.groupby(['DIVISION_NAME', 'TENURE_BIN'], observed=False).size().reset_index(name='COUNT')
    office_summary = snapshot_df.groupby(['DIVISION_NAME', 'OFFICE_NAME', 'TENURE_BIN'], observed=False).size().reset_index(name='COUNT')
    
    # 직무별 집계
    job_l1_summary = snapshot_df.groupby(['JOB_L1_NAME', 'TENURE_BIN'], observed=False).size().reset_index(name='COUNT')
    job_l2_summary = snapshot_df.groupby(['JOB_L1_NAME', 'JOB_L2_NAME', 'TENURE_BIN'], observed=False).size().reset_index(name='COUNT')

    # 직위직급별 집계
    pos_summary = snapshot_df.groupby(['POSITION_NAME', 'TENURE_BIN'], observed=False).size().reset_index(name='COUNT')
    grade_summary = snapshot_df.groupby(['POSITION_NAME', 'GRADE_ID', 'TENURE_BIN'], observed=False).size().reset_index(name='COUNT')

    # 피벗 테이블용 집계
    tenure_bins_agg = [-np.inf, 3, 7, np.inf]
    tenure_labels_agg = ['3년 이하', '3년초과~7년이하', '7년 초과']
    snapshot_df['TENURE_GROUP'] = pd.cut(snapshot_df['TENURE_YEARS'], bins=tenure_bins_agg, labels=tenure_labels_agg)
    
    return {
        "snapshot_df": snapshot_df,
        "div_summary": div_summary,
        "office_summary": office_summary,
        "job_l1_summary": job_l1_summary,
        "job_l2_summary": job_l2_summary,
        "pos_summary": pos_summary,
        "grade_summary": grade_summary
    }


@st.cache_data
def prepare_proposal_05_data():
    """
    Proposal 05 (연간 퇴사율) 분석에 필요한 데이터를 사전 가공합니다.
    - 부서별, 직무별, 직위직급별 분석 데이터를 모두 포함합니다.
    """
    base_data = load_all_base_data()
    emp_df = base_data["emp_df"]
    department_info_df = base_data["department_info_df"]
    job_info_df = base_data["job_info_df"]
    position_info_df = base_data["position_info_df"]
    
    # ... (proposal_05_부서별.py 등에서 사용했던 연도별 루프 및 계산 로직) ...
    # 이 부분은 코드가 매우 길어지므로, 실제 구현 시에는
    # proposal_05_부서별, 직무별, 직위직급별 코드의 데이터 준비 로직을
    # 여기에 통합하여 하나의 거대한 'turnover_records'를 생성하는 방식으로 구현합니다.
    # 지금은 개념적 예시로 간단히 표현합니다.

    # 이 함수가 최종적으로 반환해야 할 데이터 형태 (예시)
    analysis_df = pd.DataFrame() # 연도별, 그룹타입별, 그룹명별, 퇴사율이 담긴 long-form 데이터
    overall_turnover_df = pd.DataFrame() # 연도별 전사 평균 퇴사율 데이터
    
    # 실제로는 위 두 DataFrame을 proposal_05 시리즈 코드의 로직을 통합하여 계산해야 합니다.
    
    return {
        "analysis_df": analysis_df,
        "overall_turnover_df": overall_turnover_df
    }

# --- (이하 생략) ---
# 위와 같은 패턴으로 prepare_proposal_00_data, prepare_proposal_01_data 등
# 모든 proposal에 대한 데이터 준비 함수를 이곳에 추가합니다.
# 각 함수의 결과는 @st.cache_data로 캐싱되어야 합니다.