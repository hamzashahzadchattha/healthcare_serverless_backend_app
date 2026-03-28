"""SQL queries for the prescriptions table.

Query strings are constants. Filter clauses are composed here -- not in service.py.
No business logic. No HTTP awareness.
"""

from typing import Any

from src.shared import db
from src.shared.observability import tracer

_ACTIVE_FILTER = "AND rx.status = 'active'"
_PAST_FILTER = "AND rx.status IN ('completed', 'cancelled')"

_BASE_COUNT = """
    SELECT
        COUNT(rx.id) AS total,
        COUNT(pat.id) AS patient_found
    FROM patients pat
    LEFT JOIN prescriptions rx
           ON rx.patient_id = pat.id {filter_clause}
    WHERE pat.id = %s
      AND pat.status = 'active'
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
    FROM patients pat
    LEFT JOIN prescriptions rx
           ON rx.patient_id = pat.id {filter_clause}
    LEFT JOIN providers p ON p.id = rx.provider_id
    WHERE pat.id = %s
      AND pat.status = 'active'
    ORDER BY rx.start_date DESC NULLS LAST
    LIMIT %s OFFSET %s
"""


@tracer.capture_method
def get_prescriptions_count(patient_id: str, status_filter: str) -> dict[str, Any] | None:
    """Return a row with total and patient_found counts, or None if patient not found."""
    if status_filter == "active":
        query = _BASE_COUNT.format(filter_clause=_ACTIVE_FILTER)
    elif status_filter == "past":
        query = _BASE_COUNT.format(filter_clause=_PAST_FILTER)
    else:
        query = _BASE_COUNT.format(filter_clause="")

    rows = db.execute_query(query, (patient_id,))
    return rows[0] if rows else None


@tracer.capture_method
def get_prescriptions(
    patient_id: str, status_filter: str, limit: int, offset: int
) -> list[dict[str, Any]]:
    """Return paginated prescriptions for a patient, filtered by status_filter value.

    Filter clause is embedded in the JOIN ON condition so the WHERE clause
    filters only on the patient, preserving the LEFT JOIN semantics.
    """
    if status_filter == "active":
        query = _BASE_SELECT.format(filter_clause=_ACTIVE_FILTER)
    elif status_filter == "past":
        query = _BASE_SELECT.format(filter_clause=_PAST_FILTER)
    else:
        query = _BASE_SELECT.format(filter_clause="")

    return db.execute_query(query, (patient_id, limit, offset))
