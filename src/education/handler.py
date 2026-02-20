"""GET /patients/{patient_id}/education-videos -- Lambda entrypoint.

Parses the path parameter, delegates to service, returns HTTP response.
"""

import time
from typing import Any

from src.education import service
from src.shared import response
from src.shared.exceptions import HealthcarePlatformError
from src.shared.logger import get_logger
from src.shared.validators import parse_uuid_param


_logger = get_logger(__name__)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for GET /patients/{patient_id}/education-videos."""
    _logger.set_request_id(context.aws_request_id)
    start = time.perf_counter()
    _logger.info("Education videos request received")

    try:
        patient_id = parse_uuid_param(
            (event.get("pathParameters") or {}).get("patient_id"), "patient_id"
        )
        data = service.get_education_videos(patient_id)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.info(
            "Education videos response ready",
            count=data["total"],
            duration_ms=elapsed_ms,
        )
        return response.success(data=data)

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.warning(
            "Education videos request failed",
            error_code=exc.error_code,
            duration_ms=elapsed_ms,
        )
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.error(
            "Unexpected error fetching education videos",
            duration_ms=elapsed_ms,
            exc_info=True,
        )
        return response.error(
            message="An unexpected error occurred",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )
