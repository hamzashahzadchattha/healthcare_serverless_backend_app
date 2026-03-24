"""GET /patients/{patient_id}/prescriptions -- Lambda entrypoint.

Parses path and query parameters, delegates to service, returns HTTP response.
"""

import time
from typing import Any

from aws_lambda_powertools.metrics import MetricUnit

from src.prescriptions import service
from src.prescriptions.models import PRESCRIPTION_FILTER_VALUES
from src.shared import response
from src.shared.exceptions import HealthcarePlatformError
from src.shared.observability import logger, metrics, tracer
from src.shared.validators import parse_enum_param, parse_int_param, parse_uuid_param


@metrics.log_metrics(capture_cold_start_metric=True)
@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler(capture_response=False)
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for GET /patients/{patient_id}/prescriptions."""
    start = time.perf_counter()
    logger.info("Prescription list request received")

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
        page = parse_int_param(query_params.get("page"), "page", default=1, min_value=1)
        limit = parse_int_param(
            query_params.get("limit"), "limit", default=50, min_value=1, max_value=100
        )

        data = service.list_prescriptions(patient_id, status_filter, page, limit)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="PrescriptionsQueried", unit=MetricUnit.Count, value=1)
        metrics.add_metadata(key="filter", value=status_filter)
        logger.info(
            "Prescription list complete",
            extra={"filter": status_filter, "count": len(data["items"]), "duration_ms": elapsed_ms},
        )
        return response.success(data=data, meta={"filter": status_filter})

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.warning(
            "Prescription list failed",
            extra={"error_code": exc.error_code, "duration_ms": elapsed_ms},
        )
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="UnhandledException", unit=MetricUnit.Count, value=1)
        logger.exception(
            "Unexpected error listing prescriptions",
            extra={"duration_ms": elapsed_ms},
        )
        return response.error(
            message="An unexpected error occurred",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )
