"""Appointment Lambda entrypoints -- upcoming retrieval and provider notes upload.

Both handlers live here because they share the same feature directory and IAM role.
Each handler is a thin wrapper: parse, call service, respond, catch exceptions.
"""

import time
from typing import Any

from src.appointments import notes_service, upcoming_service
from src.appointments.models import ProviderNoteRequest
from src.shared import response
from src.shared.exceptions import HealthcarePlatformError
from src.shared.logger import get_logger
from src.shared.validators import parse_body, parse_int_param, parse_uuid_param


_logger = get_logger(__name__)


def upcoming_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for GET /patients/{patient_id}/appointments/upcoming."""
    _logger.set_request_id(context.aws_request_id)
    start = time.perf_counter()
    _logger.info("Upcoming appointments request received")

    try:
        query_params = event.get("queryStringParameters") or {}
        patient_id = parse_uuid_param(
            (event.get("pathParameters") or {}).get("patient_id"), "patient_id"
        )
        page = parse_int_param(query_params.get("page"), "page", default=1, min_value=1)
        limit = parse_int_param(query_params.get("limit"), "limit", default=50, min_value=1, max_value=100)

        data = upcoming_service.get_upcoming_appointments(patient_id, page, limit)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.info(
            "Upcoming appointments response ready",
            count=len(data["items"]),
            duration_ms=elapsed_ms,
        )
        return response.success(data=data)

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.warning(
            "Upcoming appointments request failed",
            error_code=exc.error_code,
            duration_ms=elapsed_ms,
        )
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.error(
            "Unexpected error fetching upcoming appointments",
            duration_ms=elapsed_ms,
            exc_info=True,
        )
        return response.error(
            message="An unexpected error occurred",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )


def notes_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for POST /appointments/{appointment_id}/notes."""
    _logger.set_request_id(context.aws_request_id)
    start = time.perf_counter()
    _logger.info("Provider note upload request received")

    try:
        appointment_id = parse_uuid_param(
            (event.get("pathParameters") or {}).get("appointment_id"),
            "appointment_id",
        )
        payload = parse_body(event.get("body"), ProviderNoteRequest)
        data = notes_service.upload_note(appointment_id, payload)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.info(
            "Provider note upload complete",
            appointment_id=appointment_id,
            duration_ms=elapsed_ms,
        )
        return response.success(data=data, status_code=201)

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.warning(
            "Provider note upload failed",
            error_code=exc.error_code,
            duration_ms=elapsed_ms,
        )
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.error(
            "Unexpected error uploading provider note",
            duration_ms=elapsed_ms,
            exc_info=True,
        )
        return response.error(
            message="An unexpected error occurred",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )
