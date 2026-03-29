"""POST /auth/verify — confirm signup with the OTP sent by Cognito."""

import time
from typing import Any

from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError

from src.auth.service import (
    CLIENT_ID,
    _VERIFY_ERRORS,
    cognito_client,
    cognito_error_to_app_exception,
    parse_body,
    require_fields,
)
from src.shared import response
from src.shared.exceptions import HealthcarePlatformError
from src.shared.observability import logger, metrics, tracer


@metrics.log_metrics(capture_cold_start_metric=True)
@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler(capture_response=False)
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for POST /auth/verify."""
    start = time.perf_counter()
    logger.info("Verify OTP request received")
    cognito_exc: ClientError | None = None

    try:
        body = parse_body(event)
        require_fields(body, "email", "code")

        try:
            cognito_client.confirm_sign_up(
                ClientId=CLIENT_ID,
                Username=body["email"],
                ConfirmationCode=body["code"],
            )
        except ClientError as exc:
            cognito_exc = exc

        if cognito_exc is not None:
            raise cognito_error_to_app_exception(cognito_exc, _VERIFY_ERRORS)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="VerifySuccess", unit=MetricUnit.Count, value=1)
        logger.info("Email verified", extra={"duration_ms": elapsed_ms})
        return response.success(data={"message": "Email verified. You can now sign in."})

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="VerifyError", unit=MetricUnit.Count, value=1)
        logger.warning("Verify failed", extra={"error_code": exc.error_code, "duration_ms": elapsed_ms})
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="UnhandledException", unit=MetricUnit.Count, value=1)
        logger.exception("Unexpected error in verify", extra={"duration_ms": elapsed_ms})
        return response.error(message="An unexpected error occurred", error_code="INTERNAL_ERROR", status_code=500)
