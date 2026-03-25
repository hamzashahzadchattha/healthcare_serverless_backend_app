"""POST /patients/register -- Lambda entrypoint.

Responsibilities: parse event, call service, build HTTP response, handle exceptions.
No business logic. No SQL. No hashing.
"""

import os
import json
import time
from typing import Any

from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.idempotency import (
    DynamoDBPersistenceLayer,
    IdempotencyConfig,
    idempotent,
)
from aws_lambda_powertools.utilities.parser import ValidationError as PowertoolsValidationError
from aws_lambda_powertools.utilities.parser import parse as powertools_parse

from src.patients import service
from src.patients.models import PatientRegistrationRequest
from src.shared import response
from src.shared.exceptions import HealthcarePlatformError, ValidationError as AppValidationError
from src.shared.observability import logger, metrics, tracer

# # Module-level — initialised once per container, reused across warm invocations.
# _idempotency_table_name = os.environ.get("IDEMPOTENCY_TABLE_NAME")
# _persistence_layer = (
#     DynamoDBPersistenceLayer(table_name=_idempotency_table_name)
#     if _idempotency_table_name
#     else None
# )
# _idempotency_config = IdempotencyConfig(
#     event_key_jmespath="body",      # Idempotency key derived from the request body
#     expires_after_seconds=3600,     # 1-hour dedup window
# )
# _idempotent_decorator = (
#     idempotent(config=_idempotency_config, persistence_store=_persistence_layer)
#     if _persistence_layer is not None
#     else (lambda fn: fn)
# )


@metrics.log_metrics(capture_cold_start_metric=True)
@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler(capture_response=False)
# @_idempotent_decorator
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for POST /patients/register."""
    start = time.perf_counter()
    logger.info("Patient registration request received")

    try:
        body_raw = event.get("body")
        if not body_raw:
            # Preserve existing behaviour from src.shared.validators.parse_body
            raise AppValidationError("Request body is required")

        try:
            body_data = json.loads(body_raw)
        except json.JSONDecodeError as exc:
            raise AppValidationError("Request body must be valid JSON") from exc

        try:
            payload = powertools_parse(
                model=PatientRegistrationRequest,
                event=body_data,
            )
        except PowertoolsValidationError as exc:
            messages = [
                f"Field '{'.'.join(str(loc) for loc in err.get('loc', []))}': {err.get('msg', '')}"
                for err in exc.errors()
            ]
            raise AppValidationError(
                "Request body validation failed",
                details={"field_errors": messages},
            ) from exc

        result = service.register_patient(payload)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="PatientRegistrationSuccess", unit=MetricUnit.Count, value=1)
        metrics.add_metadata(key="duration_ms", value=elapsed_ms)
        logger.info(
            "Patient registration complete",
            extra={"patient_id": result.patient_id, "duration_ms": elapsed_ms},
        )
        return response.success(data=result.model_dump(), status_code=201)

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="PatientRegistrationError", unit=MetricUnit.Count, value=1)
        logger.warning(
            "Patient registration failed",
            extra={"error_code": exc.error_code, "duration_ms": elapsed_ms},
        )
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="UnhandledException", unit=MetricUnit.Count, value=1)
        logger.exception(
            "Unexpected error in patient registration",
            extra={"duration_ms": elapsed_ms},
        )
        return response.error(
            message="An unexpected error occurred",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )
