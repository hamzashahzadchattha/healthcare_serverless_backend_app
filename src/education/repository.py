"""SQL queries for patient_conditions table.

Provides condition data used to drive YouTube video recommendations.
"""

from typing import Any

from src.shared import db
from src.shared.observability import tracer

_SELECT_ACTIVE_CONDITIONS = """
    SELECT DISTINCT condition_name, icd10_code
    FROM patient_conditions
    WHERE patient_id = %s AND status IN ('active', 'chronic')
"""


@tracer.capture_method
def get_active_conditions(patient_id: str) -> list[dict[str, Any]]:
    """Return all distinct active conditions for a patient."""
    return db.execute_query(_SELECT_ACTIVE_CONDITIONS, (patient_id,))
