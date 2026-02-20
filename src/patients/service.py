"""Business logic for patient registration.

Knows about hashing, uniqueness rules, and data transformation.
Does not know about HTTP events or SQL syntax.
"""

import hashlib

import bcrypt

from src.patients import repository
from src.patients.models import PatientRegistrationRequest, PatientRegistrationResponse
from src.shared.exceptions import DuplicateRecordError
from src.shared.logger import get_logger

_logger = get_logger(__name__)

_BCRYPT_ROUNDS = 12


def _bcrypt_hash(value: str) -> str:
    """Return a bcrypt hash of value using the configured work factor."""
    return bcrypt.hashpw(value.encode(), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode()


def _sha256_hex(value: str) -> str:
    """Return a hex SHA-256 digest used for O(1) uniqueness lookups."""
    return hashlib.sha256(value.encode()).hexdigest()


def register_patient(payload: PatientRegistrationRequest) -> PatientRegistrationResponse:
    """Orchestrate patient registration: uniqueness check, hashing, persistence.

    Args:
        payload: Validated and normalised registration request from the handler.

    Returns:
        PatientRegistrationResponse with the new patient_id and status.

    Raises:
        DuplicateRecordError: When the email is already registered.
    """
    email_sha256 = _sha256_hex(payload.email)

    existing = repository.find_by_email_sha256(email_sha256)
    if existing:
        raise DuplicateRecordError("A patient with this email address is already registered")

    row = repository.insert_patient(
        first_name=payload.first_name,
        last_name=payload.last_name,
        dob_hash=_bcrypt_hash(payload.dob.isoformat()),
        email_hash=_bcrypt_hash(payload.email),
        email_sha256=email_sha256,
        phone_hash=_bcrypt_hash(payload.phone),
    )

    _logger.info("Patient record created", patient_id=str(row["id"]))
    return PatientRegistrationResponse(patient_id=str(row["id"]), status=row["status"])
