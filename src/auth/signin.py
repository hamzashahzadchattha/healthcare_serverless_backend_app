"""POST /auth/signin — authenticate and return Cognito tokens."""

import time
from typing import Any

from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError

from src.auth.service import CLIENT_ID, cognito_client, parse_body, require_fields
from src.shared import response
from src.shared.exceptions import HealthcarePlatformError, UnauthorizedError, ValidationError
from src.shared.observability import logger, metrics, tracer


@metrics.log_metrics(capture_cold_start_metric=True)
@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler(capture_response=False)
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Authenticate with email/password and return Cognito tokens."""
    start = time.perf_counter()
    logger.info("Signin request received")

    try:
        body = parse_body(event)
        require_fields(body, "email", "password")

        result = cognito_client.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": body["email"],
                "PASSWORD": body["password"],
            },
        )

        auth = result["AuthenticationResult"]
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="SigninSuccess", unit=MetricUnit.Count, value=1)
        logger.info("Signin complete", extra={"duration_ms": elapsed_ms})
        return response.success(data={
            "access_token": auth["AccessToken"],
            "id_token": auth["IdToken"],
            "refresh_token": auth["RefreshToken"],
            "expires_in": auth["ExpiresIn"],
            "token_type": auth["TokenType"],
        })

    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("NotAuthorizedException", "UserNotFoundException"):
            raise UnauthorizedError("Invalid email or password") from exc
        if code == "UserNotConfirmedException":
            raise ValidationError("Email not verified. Check your inbox for the verification code.") from exc
        if code == "PasswordResetRequiredException":
            raise ValidationError("Password reset required") from exc
        raise

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.warning("Signin failed", extra={"error_code": exc.error_code, "duration_ms": elapsed_ms})
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="UnhandledException", unit=MetricUnit.Count, value=1)
        logger.exception("Unexpected error in signin", extra={"duration_ms": elapsed_ms})
        return response.error(message="An unexpected error occurred", error_code="INTERNAL_ERROR", status_code=500)
