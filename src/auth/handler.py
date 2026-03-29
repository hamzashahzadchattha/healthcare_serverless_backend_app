"""Cognito auth endpoints — signup, verify, signin, logout.

All operations call Cognito directly via boto3. No VPC or RDS access needed.
"""

import json
import os
import time
from typing import Any

import boto3
from aws_lambda_powertools.metrics import MetricUnit
from botocore.exceptions import ClientError

from src.shared import response
from src.shared.exceptions import (
    DuplicateRecordError,
    HealthcarePlatformError,
    UnauthorizedError,
    ValidationError,
)
from src.shared.observability import logger, metrics, tracer

# Module-level client — reused across warm invocations
_cognito = boto3.client("cognito-idp", region_name=os.environ.get("REGION", "us-east-1"))
_CLIENT_ID = os.environ.get("COGNITO_APP_CLIENT_ID", "")


def _parse_body(event: dict[str, Any]) -> dict[str, Any]:
    """Parse and return the JSON request body, raising ValidationError on failure."""
    raw = event.get("body")
    if not raw:
        raise ValidationError("Request body is required")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError("Request body must be valid JSON") from exc


def _require(body: dict[str, Any], *fields: str) -> None:
    """Raise ValidationError if any required field is missing or blank."""
    missing = [f for f in fields if not body.get(f)]
    if missing:
        raise ValidationError(
            "Missing required fields",
            details={"missing": missing},
        )


@metrics.log_metrics(capture_cold_start_metric=True)
@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler(capture_response=False)
def signup_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """POST /auth/signup — register a new user in Cognito.

    Body: { "email": str, "password": str }
    Cognito sends a verification OTP to the email automatically.
    """
    start = time.perf_counter()
    logger.info("Signup request received")

    try:
        body = _parse_body(event)
        _require(body, "email", "password")

        _cognito.sign_up(
            ClientId=_CLIENT_ID,
            Username=body["email"],
            Password=body["password"],
            UserAttributes=[{"Name": "email", "Value": body["email"]}],
        )

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="SignupSuccess", unit=MetricUnit.Count, value=1)
        logger.info("Signup complete", extra={"duration_ms": elapsed_ms})
        return response.success(
            data={"message": "Verification code sent to your email"},
            status_code=201,
        )

    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "UsernameExistsException":
            raise DuplicateRecordError("An account with this email already exists") from exc
        if code == "InvalidPasswordException":
            raise ValidationError("Password does not meet requirements") from exc
        if code == "InvalidParameterException":
            raise ValidationError(exc.response["Error"]["Message"]) from exc
        raise

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.warning("Signup failed", extra={"error_code": exc.error_code, "duration_ms": elapsed_ms})
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="UnhandledException", unit=MetricUnit.Count, value=1)
        logger.exception("Unexpected error in signup", extra={"duration_ms": elapsed_ms})
        return response.error(message="An unexpected error occurred", error_code="INTERNAL_ERROR", status_code=500)


@metrics.log_metrics(capture_cold_start_metric=True)
@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler(capture_response=False)
def verify_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """POST /auth/verify — confirm signup with the OTP sent by Cognito.

    Body: { "email": str, "code": str }
    """
    start = time.perf_counter()
    logger.info("Verify OTP request received")

    try:
        body = _parse_body(event)
        _require(body, "email", "code")

        _cognito.confirm_sign_up(
            ClientId=_CLIENT_ID,
            Username=body["email"],
            ConfirmationCode=body["code"],
        )

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="VerifySuccess", unit=MetricUnit.Count, value=1)
        logger.info("Email verified", extra={"duration_ms": elapsed_ms})
        return response.success(data={"message": "Email verified. You can now sign in."})

    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("CodeMismatchException", "ExpiredCodeException"):
            raise ValidationError("Invalid or expired verification code") from exc
        if code == "UserNotFoundException":
            raise ValidationError("No account found for this email") from exc
        if code == "NotAuthorizedException":
            raise ValidationError("Account is already confirmed") from exc
        raise

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.warning("Verify failed", extra={"error_code": exc.error_code, "duration_ms": elapsed_ms})
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="UnhandledException", unit=MetricUnit.Count, value=1)
        logger.exception("Unexpected error in verify", extra={"duration_ms": elapsed_ms})
        return response.error(message="An unexpected error occurred", error_code="INTERNAL_ERROR", status_code=500)


@metrics.log_metrics(capture_cold_start_metric=True)
@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler(capture_response=False)
def signin_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """POST /auth/signin — authenticate and return Cognito tokens.

    Body: { "email": str, "password": str }
    Returns: { "access_token", "id_token", "refresh_token", "expires_in" }
    """
    start = time.perf_counter()
    logger.info("Signin request received")

    try:
        body = _parse_body(event)
        _require(body, "email", "password")

        result = _cognito.initiate_auth(
            ClientId=_CLIENT_ID,
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


@metrics.log_metrics(capture_cold_start_metric=True)
@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler(capture_response=False)
def logout_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """POST /auth/logout — globally revoke the caller's Cognito tokens.

    Requires: Authorization: Bearer <access_token>
    """
    start = time.perf_counter()
    logger.info("Logout request received")

    try:
        headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
        auth_header = headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            raise UnauthorizedError("Authorization header missing or malformed")

        access_token = auth_header[len("Bearer "):]

        _cognito.global_sign_out(AccessToken=access_token)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="LogoutSuccess", unit=MetricUnit.Count, value=1)
        logger.info("Logout complete", extra={"duration_ms": elapsed_ms})
        return response.success(data={"message": "Signed out successfully"})

    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "NotAuthorizedException":
            raise UnauthorizedError("Invalid or expired access token") from exc
        raise

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.warning("Logout failed", extra={"error_code": exc.error_code, "duration_ms": elapsed_ms})
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        metrics.add_metric(name="UnhandledException", unit=MetricUnit.Count, value=1)
        logger.exception("Unexpected error in logout", extra={"duration_ms": elapsed_ms})
        return response.error(message="An unexpected error occurred", error_code="INTERNAL_ERROR", status_code=500)
