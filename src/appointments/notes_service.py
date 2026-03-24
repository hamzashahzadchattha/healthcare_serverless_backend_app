"""Business logic for provider note uploads.

Enforces appointment status and provider ownership rules.
"""

from typing import Any

from src.appointments import repository
from src.appointments.models import ProviderNoteRequest
from src.shared.exceptions import ForbiddenError, RecordNotFoundError, ValidationError
from src.shared.observability import logger, tracer


@tracer.capture_method
def upload_note(appointment_id: str, payload: ProviderNoteRequest) -> dict[str, Any]:
    """Validate ownership and status rules then persist the provider note.

    Args:
        appointment_id: Validated UUID string from the request path.
        payload: Validated ProviderNoteRequest from the handler.

    Returns:
        Dict with note_id, appointment_id, and created_at.

    Raises:
        RecordNotFoundError: When appointment does not exist.
        ValidationError: When appointment is not in 'completed' status.
        ForbiddenError: When provider_id does not match the appointment's provider.
    """
    appt = repository.get_appointment_by_id(appointment_id)
    if appt is None:
        raise RecordNotFoundError("Appointment not found")

    if appt["status"] != "completed":
        raise ValidationError("Notes can only be added to completed appointments")

    if str(appt["provider_id"]) != payload.provider_id:
        raise ForbiddenError("Provider is not authorised to add notes to this appointment")

    note = repository.insert_note_with_timestamp(
        appointment_id=appointment_id,
        provider_id=payload.provider_id,
        note_text=payload.note_text,
    )

    logger.info(
        "Provider note uploaded",
        extra={"appointment_id": appointment_id, "note_id": str(note["id"])},
    )
    return {
        "note_id": str(note["id"]),
        "appointment_id": appointment_id,
        "created_at": note["created_at"].isoformat(),
    }
