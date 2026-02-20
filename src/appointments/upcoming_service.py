"""Business logic for upcoming appointments retrieval.

Validates patient access and formats appointment rows for the API response.
"""

from typing import Any

from src.appointments import repository
from src.shared.exceptions import RecordNotFoundError
from src.shared.logger import get_logger


_logger = get_logger(__name__)


def _format_appointment(row: dict[str, Any]) -> dict[str, Any]:
    """Transform a flat DB row into the nested appointment response shape."""
    return {
        "appointment_id": str(row["appointment_id"]),
        "provider": {
            "provider_id": str(row["provider_id"]),
            "full_name": f"Dr. {row['provider_first_name']} {row['provider_last_name']}",
            "specialty": row["provider_specialty"],
        },
        "scheduled_at": row["scheduled_at"].isoformat(),
        "duration_minutes": row["duration_minutes"],
        "appointment_type": row["appointment_type"],
        "status": row["status"],
    }


def get_upcoming_appointments(patient_id: str) -> dict[str, Any]:
    """Fetch and format upcoming appointments for a patient.

    Args:
        patient_id: Validated UUID string from the request path.

    Returns:
        Dict with 'appointments' list and 'total' count.

    Raises:
        RecordNotFoundError: When patient_id does not exist.
    """
    if not repository.patient_exists(patient_id):
        raise RecordNotFoundError("Patient not found")

    rows = repository.get_upcoming_appointments(patient_id)
    appointments = [_format_appointment(row) for row in rows]

    _logger.info(
        "Upcoming appointments fetched",
        patient_id=patient_id,
        count=len(appointments),
    )
    return {"appointments": appointments, "total": len(appointments)}
