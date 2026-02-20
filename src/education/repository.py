"""SQL queries for patient_conditions table.

Provides condition data used to drive YouTube video recommendations.
"""

from typing import Any

from src.shared import db


_CHECK_PATIENT_EXISTS = """
    SELECT id FROM patients WHERE id = %s AND status = 'active'
"""

_SELECT_ACTIVE_CONDITIONS = """
    SELECT DISTINCT condition_name, icd10_code
    FROM patient_conditions
    WHERE patient_id = %s AND status IN ('active', 'chronic')
"""


def patient_exists(patient_id: str) -> bool:
    """Return True when an active patient record exists."""
    rows = db.execute_query(_CHECK_PATIENT_EXISTS, (patient_id,))
    return len(rows) > 0


def get_active_conditions(patient_id: str) -> list[dict[str, Any]]:
    """Return all distinct active conditions for a patient."""
    return db.execute_query(_SELECT_ACTIVE_CONDITIONS, (patient_id,))
