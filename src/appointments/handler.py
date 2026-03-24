"""Appointment Lambda entrypoints -- upcoming retrieval and provider notes upload.

Both handlers live here because they share the same feature directory and IAM role.
Each handler is a thin wrapper: parse, call service, respond, catch exceptions.
"""

import time
from typing import Any

from aws_lambda_powertools.metrics import MetricUnit

from src.appointments import notes_service, upcoming_service
from src.appointments.models import ProviderNoteRequest
from src.shared import response
from src.shared.exceptions import HealthcarePlatformError
from src.shared.observability import logger, metrics, tracer
from src.shared.validators import parse_body, parse_int_param, parse_uuid_param


@metrics.log_metrics(capture_cold_start_metric=True)
@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler(capture_response=False)
def upcoming_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for GET /patients/{patient_id}/appointments/upcoming."""
    start = time.perf_counter()
    logger.info("Upcoming appointments request received")

    try:
        query_params = event.get("queryStringParameters") or {}
        patient_id = parse_uuid_param(
            (event.get("pathParameters") or {}).get("patient_id"), "patient_id"
        )
        page = parse_int_param(query_params.get("page"), "page", default=1, min_value=1)
        limit = parse_int_param(
            query_params.get("limit"), "limit", default=50, min_value=1, max_value=100
        )

        data = upcoming_service.get_upcoming_appointments(patient_id, page, limit)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="AppointmentsQueried", unit=MetricUnit.Count, value=1)
        metrics.add_metadata(key="count", value=len(data["items"]))
        logger.info(
            "Upcoming appointments response ready",
            extra={"count": len(data["items"]), "duration_ms": elapsed_ms},
        )
        return response.success(data=data)

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.warning(
            "Upcoming appointments request failed",
            extra={"error_code": exc.error_code, "duration_ms": elapsed_ms},
        )
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="UnhandledException", unit=MetricUnit.Count, value=1)
        logger.exception(
            "Unexpected error fetching upcoming appointments",
            extra={"duration_ms": elapsed_ms},
        )
        return response.error(
            message="An unexpected error occurred",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )


@metrics.log_metrics(capture_cold_start_metric=True)
@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler(capture_response=False)
def notes_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for POST /appointments/{appointment_id}/notes."""
    start = time.perf_counter()
    logger.info("Provider note upload request received")

    try:
        appointment_id = parse_uuid_param(
            (event.get("pathParameters") or {}).get("appointment_id"),
            "appointment_id",
        )
        payload = parse_body(event.get("body"), ProviderNoteRequest)
        data = notes_service.upload_note(appointment_id, payload)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="ProviderNotesUploaded", unit=MetricUnit.Count, value=1)
        logger.info(
            "Provider note upload complete",
            extra={"appointment_id": appointment_id, "duration_ms": elapsed_ms},
        )
        return response.success(data=data, status_code=201)

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.warning(
            "Provider note upload failed",
            extra={"error_code": exc.error_code, "duration_ms": elapsed_ms},
        )
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="UnhandledException", unit=MetricUnit.Count, value=1)
        logger.exception(
            "Unexpected error uploading provider note",
            extra={"duration_ms": elapsed_ms},
        )
        return response.error(
            message="An unexpected error occurred",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )
