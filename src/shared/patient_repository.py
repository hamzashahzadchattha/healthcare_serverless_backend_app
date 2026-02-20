"""Shared patient existence check used across multiple feature services.

Centralised here to avoid duplicating the same SQL and function in
appointments, prescriptions, and education repositories.
"""

from src.shared import db

_SELECT_PATIENT_EXISTS = """
    SELECT id FROM patients WHERE id = %s AND status = 'active'
"""


def patient_exists(patient_id: str) -> bool:
    """Return True when an active patient record exists for patient_id."""
    rows = db.execute_query(_SELECT_PATIENT_EXISTS, (patient_id,))
    return len(rows) > 0
