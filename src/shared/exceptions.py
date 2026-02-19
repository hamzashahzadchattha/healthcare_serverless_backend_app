"""Typed exception hierarchy for the healthcare platform."""

from typing import Any


class HealthcarePlatformError(Exception):
    """Base class for all application-level exceptions."""

    http_status: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(HealthcarePlatformError):
    """Request payload failed JSON Schema validation or business rule checks."""

    http_status = 400
    error_code = "VALIDATION_ERROR"


class RecordNotFoundError(HealthcarePlatformError):
    """Requested resource does not exist or the caller does not have access to it."""

    http_status = 404
    error_code = "NOT_FOUND"


class DuplicateRecordError(HealthcarePlatformError):
    """Attempt to create a record that violates a unique constraint."""

    http_status = 409
    error_code = "DUPLICATE_RECORD"


class UnauthorizedError(HealthcarePlatformError):
    """Caller is not authenticated or the JWT is invalid."""

    http_status = 401
    error_code = "UNAUTHORIZED"


class ForbiddenError(HealthcarePlatformError):
    """Caller is authenticated but does not have permission for this resource."""

    http_status = 403
    error_code = "FORBIDDEN"


class DatabaseConnectionError(HealthcarePlatformError):
    """Could not establish a connection to the RDS instance."""

    http_status = 503
    error_code = "DATABASE_UNAVAILABLE"


class DatabaseQueryError(HealthcarePlatformError):
    """A SQL query failed due to a constraint violation or unexpected DB error."""

    http_status = 500
    error_code = "DATABASE_ERROR"


class SecretsManagerError(HealthcarePlatformError):
    """Could not retrieve a secret from AWS Secrets Manager."""

    http_status = 503
    error_code = "SECRETS_UNAVAILABLE"


class ExternalServiceError(HealthcarePlatformError):
    """An upstream external service returned an error."""

    http_status = 502
    error_code = "EXTERNAL_SERVICE_ERROR"


class RateLimitExceededError(HealthcarePlatformError):
    """External API rate limit was hit."""

    http_status = 429
    error_code = "RATE_LIMIT_EXCEEDED"
