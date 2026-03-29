"""SQL queries and data access functions for the admin patient management API."""

from typing import Any

from src.shared import db
from src.shared.observability import tracer

_SELECT_ALL_PATIENTS = """
    SELECT id, first_name, last_name, status, created_at, cognito_sub
    FROM patients
    ORDER BY created_at DESC
    LIMIT %s OFFSET %s
"""

_COUNT_ALL_PATIENTS = "SELECT COUNT(id) AS total FROM patients"

_SELECT_PATIENT_BY_ID = """
    SELECT id, first_name, last_name, status, created_at, updated_at, cognito_sub
    FROM patients
    WHERE id = %s
"""


@tracer.capture_method
def list_patients(page: int, limit: int) -> dict[str, Any]:
    """Return a paginated list of all patients with total count."""
    offset = (page - 1) * limit
    count_rows = db.execute_query(_COUNT_ALL_PATIENTS)
    total = count_rows[0]["total"] if count_rows else 0
    rows = db.execute_query(_SELECT_ALL_PATIENTS, (limit, offset))
    return {"items": rows, "total": total, "page": page, "limit": limit}


@tracer.capture_method
def get_patient_by_id(patient_id: str) -> dict[str, Any] | None:
    """Return a single patient row by ID, or None if not found."""
    rows = db.execute_query(_SELECT_PATIENT_BY_ID, (patient_id,))
    return rows[0] if rows else None
