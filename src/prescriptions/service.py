"""Business logic for prescription listing.

Validates patient access and formats prescription rows.
Does not contain SQL. Does not know about HTTP.
"""

from typing import Any

from src.prescriptions import repository
from src.shared.exceptions import RecordNotFoundError
from src.shared.logger import get_logger


_logger = get_logger(__name__)


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


def list_prescriptions(patient_id: str, status_filter: str) -> dict[str, Any]:
    """Fetch and format prescriptions for a patient.

    Args:
        patient_id: Validated UUID string.
        status_filter: One of 'active', 'past', 'all'.

    Returns:
        Dict with 'prescriptions' list, 'total' count.

    Raises:
        RecordNotFoundError: When patient_id does not correspond to an active patient.
    """
    if not repository.patient_exists(patient_id):
        raise RecordNotFoundError("Patient not found")

    rows = repository.get_prescriptions(patient_id, status_filter)
    prescriptions = [_format_prescription(row) for row in rows]

    _logger.info(
        "Prescriptions fetched",
        patient_id=patient_id,
        filter=status_filter,
        count=len(prescriptions),
    )
    return {"prescriptions": prescriptions, "total": len(prescriptions)}
