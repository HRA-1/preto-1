import streamlit as st

# --------------------------------------------------------------------------
# HR Core Group (21개)
# --------------------------------------------------------------------------
from services.tables.HR_Core.department_table import department_df
from services.tables.HR_Core.position_table import position_df
from services.tables.HR_Core.job_table import job_df
from services.tables.HR_Core.project_table import pjt_df
from services.tables.HR_Core.absence_table import absence_df
from services.tables.HR_Core.career_table import career_df
from services.tables.HR_Core.school_table import school_df
from services.tables.HR_Core.corporation_branch_table import corp_branch_df
from services.tables.HR_Core.region_table import region_df
from services.tables.HR_Core.basic_info_table import emp_df
from services.tables.HR_Core.department_info_table import department_info_df
from services.tables.HR_Core.position_info_table import position_info_df
from services.tables.HR_Core.job_info_table import job_info_df
from services.tables.HR_Core.pjt_info_table import pjt_info_df
from services.tables.HR_Core.absence_info_table import absence_info_df
from services.tables.HR_Core.career_info_table import career_info_df
from services.tables.HR_Core.school_info_table import school_info_df
from services.tables.HR_Core.corp_branch_info_table import corp_branch_info_df
from services.tables.HR_Core.region_info_table import region_info_df
from services.tables.HR_Core.contract_info_table import contract_info_df
from services.tables.HR_Core.salary_contract_info_table import salary_contract_info_df

# --------------------------------------------------------------------------
# Time Attendance Group (7개)
# --------------------------------------------------------------------------
from services.tables.Time_Attendance.working_system_table import work_sys_df
from services.tables.Time_Attendance.working_type_table import work_type_df
from services.tables.Time_Attendance.working_info_table import work_info_df
from services.tables.Time_Attendance.detailed_working_info_table import detailed_work_info_df
from services.tables.Time_Attendance.daily_working_info_table import daily_work_info_df
from services.tables.Time_Attendance.leave_type_table import leave_type_df
from services.tables.Time_Attendance.detailed_leave_info_table import detailed_leave_info_df

# --------------------------------------------------------------------------
# Performance Group (4개)
# --------------------------------------------------------------------------
from services.tables.Performance.evaluation_system_table import evaluation_system_df
from services.tables.Performance.evaluation_apply_table import evaluation_apply_df
from services.tables.Performance.evaluation_original_score_info_table import evaluation_original_score_df
from services.tables.Performance.evaluation_modified_score_info_table import evaluation_modified_score_df

# --------------------------------------------------------------------------
# Payroll Group (3개)
# --------------------------------------------------------------------------
from services.tables.Payroll.payroll_item_table import payroll_item_df
from services.tables.Payroll.detailed_monthly_payroll_info_table import detailed_monthly_payroll_df
from services.tables.Payroll.yearly_payroll_info_table import yearly_payroll_df


@st.cache_data
def load_all_base_data():
    """
    프로젝트에서 사용하는 모든 원본 DataFrame을 로드하고 딕셔너리 형태로 반환합니다.
    Streamlit의 @st.cache_data 데코레이터를 사용하여 이 함수의 결과는 캐싱되며,
    앱이 재실행될 때마다 다시 로드되지 않아 성능이 향상됩니다.
    """
    base_data = {
        # HR Core
        "department_df": department_df,
        "position_df": position_df,
        "job_df": job_df,
        "pjt_df": pjt_df,
        "absence_df": absence_df,
        "career_df": career_df,
        "school_df": school_df,
        "corp_branch_df": corp_branch_df,
        "region_df": region_df,
        "emp_df": emp_df,
        "department_info_df": department_info_df,
        "position_info_df": position_info_df,
        "job_info_df": job_info_df,
        "pjt_info_df": pjt_info_df,
        "absence_info_df": absence_info_df,
        "career_info_df": career_info_df,
        "school_info_df": school_info_df,
        "corp_branch_info_df": corp_branch_info_df,
        "region_info_df": region_info_df,
        "contract_info_df": contract_info_df,
        "salary_contract_info_df": salary_contract_info_df,

        # Time Attendance
        "work_sys_df": work_sys_df,
        "work_type_df": work_type_df,
        "work_info_df": work_info_df,
        "detailed_work_info_df": detailed_work_info_df,
        "daily_work_info_df": daily_work_info_df,
        "leave_type_df": leave_type_df,
        "detailed_leave_info_df": detailed_leave_info_df,

        # Performance
        "evaluation_system_df": evaluation_system_df,
        "evaluation_apply_df": evaluation_apply_df,
        "evaluation_original_score_df": evaluation_original_score_df,
        "evaluation_modified_score_df": evaluation_modified_score_df,

        # Payroll
        "payroll_item_df": payroll_item_df,
        "detailed_monthly_payroll_df": detailed_monthly_payroll_df,
        "yearly_payroll_df": yearly_payroll_df,
    }
    return base_data