"""GET /patients/{patient_id}/prescriptions -- Lambda entrypoint.

Parses path and query parameters, delegates to service, returns HTTP response.
"""

import time
from typing import Any

from src.prescriptions import service
from src.prescriptions.models import PRESCRIPTION_FILTER_VALUES
from src.shared import response
from src.shared.exceptions import HealthcarePlatformError
from src.shared.logger import get_logger
from src.shared.validators import parse_enum_param, parse_uuid_param


_logger = get_logger(__name__)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for GET /patients/{patient_id}/prescriptions."""
    _logger.set_request_id(context.aws_request_id)
    start = time.perf_counter()
    _logger.info("Prescription list request received")

    try:
        path_params = event.get("pathParameters") or {}
        query_params = event.get("queryStringParameters") or {}

        patient_id = parse_uuid_param(path_params.get("patient_id"), "patient_id")
        status_filter = parse_enum_param(
            query_params.get("filter"),
            "filter",
            PRESCRIPTION_FILTER_VALUES,
            default="active",
        )

        data = service.list_prescriptions(patient_id, status_filter)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.info(
            "Prescription list complete",
            filter=status_filter,
            count=data["total"],
            duration_ms=elapsed_ms,
        )
        return response.success(data=data, meta={"filter": status_filter})

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.warning(
            "Prescription list failed",
            error_code=exc.error_code,
            duration_ms=elapsed_ms,
        )
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.error(
            "Unexpected error listing prescriptions",
            duration_ms=elapsed_ms,
            exc_info=True,
        )
        return response.error(
            message="An unexpected error occurred",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )
