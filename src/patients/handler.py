"""POST /patients/register -- Lambda entrypoint.

Responsibilities: parse event, call service, build HTTP response, handle exceptions.
No business logic. No SQL. No hashing.
"""

import os
import time
from typing import Any

from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.idempotency import (
    DynamoDBPersistenceLayer,
    IdempotencyConfig,
    idempotent,
)

from src.patients import service
from src.patients.models import PatientRegistrationRequest
from src.shared import response
from src.shared.exceptions import HealthcarePlatformError
from src.shared.observability import logger, metrics, tracer
from src.shared.validators import parse_body

# Module-level — initialised once per container, reused across warm invocations.
_persistence_layer = DynamoDBPersistenceLayer(
    table_name=os.environ.get("IDEMPOTENCY_TABLE_NAME", "")
)
_idempotency_config = IdempotencyConfig(
    event_key_jmespath="body",      # Idempotency key derived from the request body
    expires_after_seconds=3600,     # 1-hour dedup window
)


@metrics.log_metrics(capture_cold_start_metric=True)
@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler(capture_response=False)
@idempotent(config=_idempotency_config, persistence_store=_persistence_layer)
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for POST /patients/register."""
    start = time.perf_counter()
    logger.info("Patient registration request received")

    try:
        payload = parse_body(event.get("body"), PatientRegistrationRequest)
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
