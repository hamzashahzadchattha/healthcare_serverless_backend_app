"""Business logic for upcoming appointments retrieval.

Validates patient access and formats appointment rows for the API response.
"""

from typing import Any

from src.appointments import repository
from src.shared.exceptions import RecordNotFoundError
from src.shared.observability import logger, tracer


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


@tracer.capture_method
def get_upcoming_appointments(patient_id: str, page: int = 1, limit: int = 50) -> dict[str, Any]:
    """Fetch and format upcoming appointments for a patient.

    Args:
        patient_id: Validated UUID string from the request path.
        page: The page number to fetch (1-indexed).
        limit: The number of items per page.

    Returns:
        Dict with 'items' list, 'total' count, and pagination metadata.

    Raises:
        RecordNotFoundError: When patient_id does not exist or is inactive.
    """
    offset = (page - 1) * limit
    count_row = repository.get_upcoming_appointments_count(patient_id)

    if not count_row:
        raise RecordNotFoundError("Patient not found")

    total_count = count_row["total"]
    rows = repository.get_upcoming_appointments(patient_id, limit, offset)

    appointments = [_format_appointment(row) for row in rows if row["appointment_id"] is not None]
    total_pages = (total_count + limit - 1) // limit if limit > 0 else 0

    logger.info(
        "Upcoming appointments fetched",
        extra={"patient_id": patient_id, "count": len(appointments), "page": page},
    )
    return {
        "items": appointments,
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
    }

"""Business logic for upcoming appointments retrieval.

Validates patient access and formats appointment rows for the API response.
"""

from typing import Any

from src.appointments import repository
from src.shared.exceptions import RecordNotFoundError
from src.shared.observability import logger, tracer


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


@tracer.capture_method
def get_upcoming_appointments(patient_id: str, page: int = 1, limit: int = 50) -> dict[str, Any]:
    """Fetch and format upcoming appointments for a patient.

    Args:
        patient_id: Validated UUID string from the request path.
        page: The page number to fetch (1-indexed).
        limit: The number of items per page.

    Returns:
        Dict with 'items' list, 'total' count, and pagination metadata.

    Raises:
        RecordNotFoundError: When patient_id does not exist or is inactive.
    """
    offset = (page - 1) * limit
    count_row = repository.get_upcoming_appointments_count(patient_id)

    if not count_row:
        raise RecordNotFoundError("Patient not found")

    total_count = count_row["total"]
    rows = repository.get_upcoming_appointments(patient_id, limit, offset)

    appointments = [_format_appointment(row) for row in rows if row["appointment_id"] is not None]
    total_pages = (total_count + limit - 1) // limit if limit > 0 else 0

    logger.info(
        "Upcoming appointments fetched",
        extra={"patient_id": patient_id, "count": len(appointments), "page": page},
    )
    return {
        "items": appointments,
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
    }
