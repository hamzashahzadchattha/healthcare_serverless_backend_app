"""POST /patients/register — creates a new patient record with hashed PII."""

import hashlib
import time
from datetime import date
from typing import Any

import bcrypt

from src.shared import db, response
from src.shared.exceptions import (
    DuplicateRecordError,
    HealthcarePlatformError,
    ValidationError,
)
from src.shared.logger import get_logger
from src.shared.request_validator import validate_body
from src.patients.schemas import PATIENT_REGISTER_SCHEMA


_logger = get_logger(__name__)

_INSERT_PATIENT = """
    INSERT INTO patients (first_name, last_name, dob_hash, email_hash, email_sha256, phone_hash)
    VALUES (%s, %s, %s, %s, %s, %s)
    RETURNING id, status
"""

_CHECK_EMAIL_UNIQUE = """
    SELECT id FROM patients WHERE email_sha256 = %s
"""


def _hash_value(value: str) -> str:
    """Return a bcrypt hash of value. Uses 12 rounds for PII protection."""
    return bcrypt.hashpw(value.encode(), bcrypt.gensalt(rounds=12)).decode()


def _sha256_hex(value: str) -> str:
    """Return a SHA-256 hex digest used for fast uniqueness checks."""
    return hashlib.sha256(value.encode()).hexdigest()


def _validate_dob(dob_str: str) -> None:
    """Raise ValidationError if dob_str is not a valid past or present date."""
    try:
        dob = date.fromisoformat(dob_str)
    except ValueError as exc:
        raise ValidationError("Field 'dob' must be a valid calendar date") from exc

    if dob > date.today():
        raise ValidationError("Field 'dob' cannot be a future date")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for POST /patients/register."""
    _logger.set_request_id(context.aws_request_id)
    start = time.perf_counter()
    _logger.info("Patient registration request received")

    try:
        body = validate_body(event.get("body"), PATIENT_REGISTER_SCHEMA)
        _validate_dob(body["dob"])

        email_normalised = body["email"].lower().strip()
        email_sha256 = _sha256_hex(email_normalised)

        existing = db.execute_query(_CHECK_EMAIL_UNIQUE, (email_sha256,))
        if existing:
            raise DuplicateRecordError(
                "A patient with this email address is already registered",
            )

        rows = db.execute_query(
            _INSERT_PATIENT,
            (
                body["first_name"],
                body["last_name"],
                _hash_value(body["dob"]),
                _hash_value(email_normalised),
                email_sha256,
                _hash_value(body["phone"]),
            ),
            fetch=True,
        )

        patient = rows[0]
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.info(
            "Patient registered successfully",
            patient_id=str(patient["id"]),
            duration_ms=elapsed_ms,
        )

        return response.success(
            data={"patient_id": str(patient["id"]), "status": patient["status"]},
            status_code=201,
        )

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.warning(
            "Patient registration failed with known error",
            error_code=exc.error_code,
            duration_ms=elapsed_ms,
        )
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.error(
            "Unexpected error during patient registration",
            duration_ms=elapsed_ms,
        )
        return response.error(
            message="An unexpected error occurred",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )
