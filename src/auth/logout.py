"""POST /auth/logout — globally revoke the caller's Cognito tokens."""

import time
from typing import Any

from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError

from src.auth.service import _LOGOUT_ERRORS, cognito_client, cognito_error_to_app_exception
from src.shared import response
from src.shared.exceptions import HealthcarePlatformError, UnauthorizedError
from src.shared.observability import logger, metrics, tracer


@metrics.log_metrics(capture_cold_start_metric=True)
@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler(capture_response=False)
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for POST /auth/logout."""
    start = time.perf_counter()
    logger.info("Logout request received")
    cognito_exc: ClientError | None = None

    try:
        headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
        auth_header = headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            raise UnauthorizedError("Authorization header missing or malformed")

        access_token = auth_header[len("Bearer "):]

        try:
            cognito_client.global_sign_out(AccessToken=access_token)
        except ClientError as exc:
            cognito_exc = exc

        if cognito_exc is not None:
            raise cognito_error_to_app_exception(cognito_exc, _LOGOUT_ERRORS)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="LogoutSuccess", unit=MetricUnit.Count, value=1)
        logger.info("Logout complete", extra={"duration_ms": elapsed_ms})
        return response.success(data={"message": "Signed out successfully"})

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="LogoutError", unit=MetricUnit.Count, value=1)
        logger.warning("Logout failed", extra={"error_code": exc.error_code, "duration_ms": elapsed_ms})
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="UnhandledException", unit=MetricUnit.Count, value=1)
        logger.exception("Unexpected error in logout", extra={"duration_ms": elapsed_ms})
        return response.error(message="An unexpected error occurred", error_code="INTERNAL_ERROR", status_code=500)
