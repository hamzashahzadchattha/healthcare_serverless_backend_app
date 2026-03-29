"""SQL queries for patient_conditions table.

Provides condition data used to drive YouTube video recommendations.
"""

from typing import Any

from src.shared import db
from src.shared.observability import tracer

_SELECT_ACTIVE_CONDITIONS = """
    SELECT
        pat.id IS NOT NULL  AS patient_found,
        pc.condition_name,
        pc.icd10_code,
        pat.cognito_sub
    FROM patients pat
    LEFT JOIN patient_conditions pc
           ON pc.patient_id = pat.id
          AND pc.status IN ('active', 'chronic')
    WHERE pat.id = %s
      AND pat.status = 'active'
"""


@tracer.capture_method
def get_active_conditions(patient_id: str) -> list[dict[str, Any]]:
    """Return all distinct active conditions for a patient."""
    return db.execute_query(_SELECT_ACTIVE_CONDITIONS, (patient_id,))
