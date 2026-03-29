"""GET /patients/{patient_id}/education-videos -- Lambda entrypoint.

Parses the path parameter, delegates to service, returns HTTP response.
"""

import time
from typing import Any

from aws_lambda_powertools.metrics import MetricUnit

from src.education import service
from src.shared import response
from src.shared.auth import assert_patient_access, require_auth
from src.shared.exceptions import HealthcarePlatformError
from src.shared.observability import logger, metrics, tracer
from src.shared.validators import parse_uuid_param


@require_auth
@metrics.log_metrics(capture_cold_start_metric=True)
@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler(capture_response=False)
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for GET /patients/{patient_id}/education-videos."""
    start = time.perf_counter()
    logger.info("Education videos request received")

    try:
        patient_id = parse_uuid_param(
            (event.get("pathParameters") or {}).get("patient_id"), "patient_id"
        )
        data = service.get_education_videos(patient_id)

        claims = (event.get("requestContext") or {}).get("authorizer", {}).get("claims", {})
        assert_patient_access(claims, data.get("cognito_sub"))
        data.pop("cognito_sub", None)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="EducationVideosServed", unit=MetricUnit.Count, value=1)
        metrics.add_metadata(key="count", value=data["total"])
        logger.info(
            "Education videos response ready",
            extra={"count": data["total"], "duration_ms": elapsed_ms},
        )
        return response.success(data=data)

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.warning(
            "Education videos request failed",
            extra={"error_code": exc.error_code, "duration_ms": elapsed_ms},
        )
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="UnhandledException", unit=MetricUnit.Count, value=1)
        logger.exception(
            "Unexpected error fetching education videos",
            extra={"duration_ms": elapsed_ms},
        )
        return response.error(
            message="An unexpected error occurred",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )
