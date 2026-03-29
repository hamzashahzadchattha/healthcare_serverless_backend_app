"""Admin Lambda entrypoints — patient list and patient detail."""

import time
from typing import Any

from aws_lambda_powertools.metrics import MetricUnit

from src.admin import repository
from src.shared import response
from src.shared.auth import require_admin
from src.shared.exceptions import HealthcarePlatformError, RecordNotFoundError
from src.shared.observability import logger, metrics, tracer
from src.shared.validators import parse_int_param, parse_uuid_param


@require_admin
@metrics.log_metrics(capture_cold_start_metric=True)
@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler(capture_response=False)
def list_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for GET /admin/patients."""
    start = time.perf_counter()
    logger.info("Admin patient list request received")

    try:
        query_params = event.get("queryStringParameters") or {}
        page = parse_int_param(query_params.get("page"), "page", default=1, min_value=1)
        limit = parse_int_param(
            query_params.get("limit"), "limit", default=50, min_value=1, max_value=100
        )

        data = repository.list_patients(page, limit)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="AdminPatientsListed", unit=MetricUnit.Count, value=1)
        metrics.add_metadata(key="count", value=len(data["items"]))
        logger.info(
            "Admin patient list response ready",
            extra={"count": len(data["items"]), "duration_ms": elapsed_ms},
        )
        return response.success(data=data)

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.warning(
            "Admin patient list request failed",
            extra={"error_code": exc.error_code, "duration_ms": elapsed_ms},
        )
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="UnhandledException", unit=MetricUnit.Count, value=1)
        logger.exception(
            "Unexpected error listing admin patients",
            extra={"duration_ms": elapsed_ms},
        )
        return response.error(
            message="An unexpected error occurred",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )


@require_admin
@metrics.log_metrics(capture_cold_start_metric=True)
@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler(capture_response=False)
def detail_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for GET /admin/patients/{patient_id}."""
    start = time.perf_counter()
    logger.info("Admin patient detail request received")

    try:
        patient_id = parse_uuid_param(
            (event.get("pathParameters") or {}).get("patient_id"), "patient_id"
        )

        patient = repository.get_patient_by_id(patient_id)
        if patient is None:
            raise RecordNotFoundError("Patient not found")

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="AdminPatientDetailFetched", unit=MetricUnit.Count, value=1)
        logger.info(
            "Admin patient detail response ready",
            extra={"duration_ms": elapsed_ms},
        )
        return response.success(data=patient)

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.warning(
            "Admin patient detail request failed",
            extra={"error_code": exc.error_code, "duration_ms": elapsed_ms},
        )
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="UnhandledException", unit=MetricUnit.Count, value=1)
        logger.exception(
            "Unexpected error fetching admin patient detail",
            extra={"duration_ms": elapsed_ms},
        )
        return response.error(
            message="An unexpected error occurred",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )
