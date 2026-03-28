"""Business logic for prescription listing.

Validates patient access and formats prescription rows.
Does not contain SQL. Does not know about HTTP.
"""

from typing import Any

from src.prescriptions import repository
from src.shared.exceptions import RecordNotFoundError
from src.shared.observability import logger, tracer


def _format_prescription(row: dict[str, Any]) -> dict[str, Any]:
    """Transform a flat DB row into the API prescription response shape."""
    return {
        "prescription_id": str(row["prescription_id"]),
        "medication_name": row["medication_name"],
        "dosage": row["dosage"],
        "frequency": row["frequency"],
        "start_date": row["start_date"].isoformat() if row["start_date"] else None,
        "end_date": row["end_date"].isoformat() if row["end_date"] else None,
        "status": row["status"],
        "prescribed_by": {
            "provider_id": str(row["provider_id"]),
            "full_name": f"Dr. {row['provider_first_name']} {row['provider_last_name']}",
        },
    }


@tracer.capture_method
def list_prescriptions(
    patient_id: str, status_filter: str, page: int = 1, limit: int = 50
) -> dict[str, Any]:
    """Fetch and format prescriptions for a patient.

    Args:
        patient_id: Validated UUID string.
        status_filter: One of 'active', 'past', 'all'.
        page: Page number (1-indexed).
        limit: Max items per page.

    Returns:
        Dict with 'items' list, 'total' count, and pagination metadata.

    Raises:
        RecordNotFoundError: When patient_id does not correspond to an active patient.
    """
    offset = (page - 1) * limit
    count_row = repository.get_prescriptions_count(patient_id, status_filter)

    if not count_row:
        raise RecordNotFoundError("Patient not found")

    total_count = count_row["total"]
    rows = repository.get_prescriptions(patient_id, status_filter, limit, offset)

    # Filter out null-prescription rows that result from a patient with zero prescriptions
    prescriptions = [_format_prescription(row) for row in rows if row["prescription_id"] is not None]
    total_pages = (total_count + limit - 1) // limit if limit > 0 else 0

    logger.info(
        "Prescriptions fetched",
        extra={"patient_id": patient_id, "filter": status_filter, "count": len(prescriptions), "page": page},
    )
    return {
        "items": prescriptions,
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
    }
