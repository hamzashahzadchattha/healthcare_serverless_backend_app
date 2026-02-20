"""POST /patients/register -- Lambda entrypoint.

Responsibilities: parse event, call service, build HTTP response, handle exceptions.
No business logic. No SQL. No hashing.
"""

import time
from typing import Any

from src.patients import service
from src.patients.models import PatientRegistrationRequest
from src.shared import response
from src.shared.exceptions import HealthcarePlatformError
from src.shared.logger import get_logger
from src.shared.validators import parse_body

_logger = get_logger(__name__)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for POST /patients/register."""
    _logger.set_request_id(context.aws_request_id)
    start = time.perf_counter()
    _logger.info("Patient registration request received")

    try:
        payload = parse_body(event.get("body"), PatientRegistrationRequest)
        result = service.register_patient(payload)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.info(
            "Patient registration complete",
            patient_id=result.patient_id,
            duration_ms=elapsed_ms,
        )

        return response.success(data=result.model_dump(), status_code=201)

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.warning(
            "Patient registration failed",
            error_code=exc.error_code,
            duration_ms=elapsed_ms,
            exc_info=True,
        )
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.error(
            "Unexpected error in patient registration",
            duration_ms=elapsed_ms,
            exc_info=True,
        )
        return response.error(
            message="An unexpected error occurred",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )
