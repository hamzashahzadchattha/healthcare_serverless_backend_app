"""SQL queries for the prescriptions table.

Query strings are constants. Filter clauses are composed here -- not in service.py.
No business logic. No HTTP awareness.
"""

from typing import Any

from src.shared import db


_CHECK_PATIENT_EXISTS = """
    SELECT id FROM patients WHERE id = %s AND status = 'active'
"""

_BASE_SELECT = """
    SELECT
        rx.id               AS prescription_id,
        rx.medication_name,
        rx.dosage,
        rx.frequency,
        rx.start_date,
        rx.end_date,
        rx.status,
        p.id                AS provider_id,
        p.first_name        AS provider_first_name,
        p.last_name         AS provider_last_name
    FROM prescriptions rx
    JOIN providers p ON p.id = rx.provider_id
    WHERE rx.patient_id = %s
"""

_ACTIVE_CLAUSE = " AND rx.status = 'active'"
_PAST_CLAUSE = " AND rx.status IN ('completed', 'cancelled')"
_ORDER_CLAUSE = " ORDER BY rx.start_date DESC"

_BASE_COUNT = """
    SELECT COUNT(rx.id) AS total
    FROM prescriptions rx
    JOIN providers p ON p.id = rx.provider_id
    WHERE rx.patient_id = %s
"""

def patient_exists(patient_id: str) -> bool:
    """Return True when an active patient record exists."""
    rows = db.execute_query(_CHECK_PATIENT_EXISTS, (patient_id,))
    return len(rows) > 0


def get_prescriptions_count(patient_id: str, status_filter: str) -> int:
    """Return total count of prescriptions for a patient, filtered by status."""
    if status_filter == "active":
        query = _BASE_COUNT + _ACTIVE_CLAUSE
    elif status_filter == "past":
        query = _BASE_COUNT + _PAST_CLAUSE
    else:
        query = _BASE_COUNT

    rows = db.execute_query(query, (patient_id,))
    return rows[0]["total"] if rows else 0

def get_prescriptions(patient_id: str, status_filter: str, limit: int, offset: int) -> list[dict[str, Any]]:
    """Return paginated prescriptions for a patient, filtered by status_filter value.

    Filter clause is appended here so SQL remains in one place.
    """
    if status_filter == "active":
        query = _BASE_SELECT + _ACTIVE_CLAUSE + _ORDER_CLAUSE
    elif status_filter == "past":
        query = _BASE_SELECT + _PAST_CLAUSE + _ORDER_CLAUSE
    else:
        query = _BASE_SELECT + _ORDER_CLAUSE

    query += " LIMIT %s OFFSET %s"
    return db.execute_query(query, (patient_id, limit, offset))
