"""POST /patients/register-dc -- benchmark variant using stdlib dataclasses only.

Identical business logic to src/patients/handler.py. Differences:
  - Validation via PatientRegistrationRequest.from_dict() — pure Python, no Pydantic
  - No powertools parser import
  - 256 MB memory allocation (vs 768 MB on the Pydantic variant)
  - Only psycopg2 + Powertools layers attached (no pydantic layer)

Purpose: measure cold-start and p99 latency difference vs the Pydantic variant
under identical load using AWS Lambda Power Tuning or X-Ray traces.
"""

import json
import time
from typing import Any

from aws_lambda_powertools.metrics import MetricUnit

from src.patients_dc import service
from src.patients_dc.models import PatientRegistrationRequest
from src.shared import response
from src.shared.exceptions import HealthcarePlatformError, ValidationError as AppValidationError
from src.shared.observability import logger, metrics, tracer


@metrics.log_metrics(capture_cold_start_metric=True, raise_on_empty_metrics=False)
@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler(capture_response=False)
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for POST /patients/register-dc."""
    start = time.perf_counter()
    logger.info("Patient registration (dc) request received")

    try:
        body_raw = event.get("body")
        if not body_raw:
            raise AppValidationError("Request body is required")

        try:
            body_data = json.loads(body_raw)
        except json.JSONDecodeError as exc:
            raise AppValidationError("Request body must be valid JSON") from exc

        try:
            payload = PatientRegistrationRequest.from_dict(body_data)
        except ValueError as exc:
            # from_dict raises ValueError with a list of field error strings
            raise AppValidationError(
                "Request body validation failed",
                details={"field_errors": exc.args[0]},
            ) from exc

        result = service.register_patient(payload)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="PatientRegistrationDcSuccess", unit=MetricUnit.Count, value=1)
        metrics.add_metadata(key="duration_ms", value=elapsed_ms)
        logger.info(
            "Patient registration (dc) complete",
            extra={"patient_id": result.patient_id, "duration_ms": elapsed_ms},
        )
        return response.success(data=result.to_dict(), status_code=201)

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="PatientRegistrationDcError", unit=MetricUnit.Count, value=1)
        logger.warning(
            "Patient registration (dc) failed",
            extra={"error_code": exc.error_code, "duration_ms": elapsed_ms},
        )
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="UnhandledException", unit=MetricUnit.Count, value=1)
        logger.exception(
            "Unexpected error in patient registration (dc)",
            extra={"duration_ms": elapsed_ms},
        )
        return response.error(
            message="An unexpected error occurred",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )
