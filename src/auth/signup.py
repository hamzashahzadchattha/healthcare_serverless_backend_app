"""POST /auth/signup — register a new user in Cognito."""

import time
from typing import Any

from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError

from src.auth.service import (
    CLIENT_ID,
    _SIGNUP_ERRORS,
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
    """Lambda handler for POST /auth/signup."""
    start = time.perf_counter()
    logger.info("Signup request received")
    cognito_exc: ClientError | None = None

    try:
        body = parse_body(event)
        require_fields(body, "email", "password")

        try:
            cognito_client.sign_up(
                ClientId=CLIENT_ID,
                Username=body["email"],
                Password=body["password"],
                UserAttributes=[{"Name": "email", "Value": body["email"]}],
            )
        except ClientError as exc:
            cognito_exc = exc

        if cognito_exc is not None:
            raise cognito_error_to_app_exception(cognito_exc, _SIGNUP_ERRORS)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="SignupSuccess", unit=MetricUnit.Count, value=1)
        logger.info("Signup complete", extra={"duration_ms": elapsed_ms})
        return response.success(
            data={"message": "Verification code sent to your email"},
            status_code=201,
        )

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="SignupError", unit=MetricUnit.Count, value=1)
        logger.warning("Signup failed", extra={"error_code": exc.error_code, "duration_ms": elapsed_ms})
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="UnhandledException", unit=MetricUnit.Count, value=1)
        logger.exception("Unexpected error in signup", extra={"duration_ms": elapsed_ms})
        return response.error(message="An unexpected error occurred", error_code="INTERNAL_ERROR", status_code=500)
