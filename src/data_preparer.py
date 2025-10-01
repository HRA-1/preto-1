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
    현재 시점의 재직자(Y)에 대한 모든 최신 정보(소속, 직위, 직무 등)를 결합한
    기본 분석 데이터프레임을 생성합니다. 여러 분석에서 재사용됩니다.
    """
    base_data = load_all_base_data()
    emp_df = base_data["emp_df"]
    position_info_df = base_data["position_info_df"]
    department_info_df = base_data["department_info_df"]
    job_info_df = base_data["job_info_df"]
    position_df = base_data["position_df"]
    job_df = base_data["job_df"]
    department_df = base_data["department_df"]
    
    # Helper data from master tables
    job_df_indexed = job_df.set_index('JOB_ID')
    parent_map_job = job_df_indexed['UP_JOB_ID'].to_dict()
    job_name_map = job_df.set_index('JOB_ID')['JOB_NAME'].to_dict()
    dept_level_map = department_df.set_index('DEP_ID')['DEP_LEVEL'].to_dict()
    parent_map_dept = department_df.set_index('DEP_ID')['UP_DEP_ID'].to_dict()
    dept_name_map = department_df.set_index('DEP_ID')['DEP_NAME'].to_dict()

    # 1. 현재 재직자 필터링 및 기본 정보 계산
    current_emps_df = emp_df[emp_df['CURRENT_EMP_YN'] == 'Y'].copy()
    current_emps_df['AGE'] = current_emps_df['PERSONAL_ID'].apply(calculate_age)
    current_emps_df['TENURE_YEARS'] = current_emps_df['DURATION'] / 365.25

    # 2. 현재 소속, 직위, 직무 정보 가져오기
    current_depts = department_info_df[department_info_df['DEP_APP_END_DATE'].isnull()][['EMP_ID', 'DEP_ID']]
    current_positions = position_info_df[position_info_df['GRADE_END_DATE'].isnull()][['EMP_ID', 'POSITION_ID', 'GRADE_ID']]
    current_jobs = job_info_df[job_info_df['JOB_APP_END_DATE'].isnull()][['EMP_ID', 'JOB_ID']]

    # 3. 모든 정보 병합
    analysis_df = pd.merge(current_emps_df, current_depts, on='EMP_ID', how='left')
    analysis_df = pd.merge(analysis_df, current_positions, on='EMP_ID', how='left')
    analysis_df = pd.merge(analysis_df, current_jobs, on='EMP_ID', how='left')

    # 4. 상위 조직, 직위/직무 이름 등 추가
    parent_info = analysis_df['DEP_ID'].apply(lambda x: find_parents(x, dept_level_map, parent_map_dept, dept_name_map))
    analysis_df = pd.concat([analysis_df, parent_info.set_index(analysis_df.index)], axis=1)
    
    analysis_df = pd.merge(analysis_df, position_df[['POSITION_ID', 'POSITION_NAME']].drop_duplicates(), on='POSITION_ID', how='left')
    
    analysis_df['JOB_L1_NAME'] = analysis_df['JOB_ID'].apply(lambda x: job_name_map.get(get_level1_ancestor(x, job_df_indexed, parent_map_job)))
    analysis_df['JOB_L2_NAME'] = analysis_df['JOB_ID'].apply(lambda x: job_name_map.get(get_level2_ancestor(x, job_df_indexed, parent_map_job)))
    
    # 5. 최종 정리
    analysis_df['OFFICE_NAME'] = analysis_df['OFFICE_NAME'].fillna('(Division 직속)')
    analysis_df = analysis_df.dropna(subset=['DIVISION_NAME', 'OFFICE_NAME', 'POSITION_NAME', 'JOB_L1_NAME', 'JOB_L2_NAME'])
    
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