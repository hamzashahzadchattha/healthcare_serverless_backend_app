"""SQL queries for appointments and appointment_notes tables.

All SQL constants and db.execute_query calls for the appointments feature.
No business logic -- only data retrieval and persistence.
"""

from typing import Any

from src.shared import db

_SELECT_UPCOMING = """
    SELECT
        a.id               AS appointment_id,
        p.id               AS provider_id,
        p.first_name       AS provider_first_name,
        p.last_name        AS provider_last_name,
        p.specialty        AS provider_specialty,
        a.scheduled_at,
        a.duration_minutes,
        a.appointment_type,
        a.status
    FROM appointments a
    JOIN providers p ON p.id = a.provider_id
    WHERE a.patient_id = %s
      AND a.status = 'scheduled'
      AND a.scheduled_at >= NOW()
    ORDER BY a.scheduled_at ASC
"""

_SELECT_UPCOMING_COUNT = """
    SELECT COUNT(a.id) AS total
    FROM appointments a
    WHERE a.patient_id = %s
      AND a.status = 'scheduled'
      AND a.scheduled_at >= NOW()
"""

_SELECT_APPOINTMENT_BY_ID = """
    SELECT id, provider_id, status FROM appointments WHERE id = %s
"""

_INSERT_NOTE = """
    INSERT INTO appointment_notes (appointment_id, provider_id, note_text)
    VALUES (%s, %s, %s)
    RETURNING id, created_at
"""

_UPDATE_APPOINTMENT_TIMESTAMP = """
    UPDATE appointments SET updated_at = NOW() WHERE id = %s
"""


def get_upcoming_appointments(patient_id: str, limit: int, offset: int) -> list[dict[str, Any]]:
    """Return an paginated list of upcoming scheduled appointments for a patient."""
    query = _SELECT_UPCOMING + " LIMIT %s OFFSET %s"
    return db.execute_query(query, (patient_id, limit, offset))


def get_upcoming_appointments_count(patient_id: str) -> int:
    """Return the total number of upcoming scheduled appointments for a patient."""
    rows = db.execute_query(_SELECT_UPCOMING_COUNT, (patient_id,))
    return rows[0]["total"] if rows else 0


def get_appointment_by_id(appointment_id: str) -> dict[str, Any] | None:
    """Return an appointment row or None if it does not exist."""
    rows = db.execute_query(_SELECT_APPOINTMENT_BY_ID, (appointment_id,))
    return rows[0] if rows else None


def insert_note_with_timestamp(
    appointment_id: str,
    provider_id: str,
    note_text: str,
) -> dict[str, Any]:
    """Insert a provider note and update the appointment timestamp atomically."""
    results = db.execute_transaction(
        [
            (_INSERT_NOTE, (appointment_id, provider_id, note_text)),
            (_UPDATE_APPOINTMENT_TIMESTAMP, (appointment_id,)),
        ]
    )
    return results[0] if results else {}
