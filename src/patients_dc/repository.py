"""SQL queries for the patients table — dataclass benchmark variant.

Identical SQL to src/patients/repository.py. Separated so the benchmark
function has no import dependency on the pydantic-based patients package.
"""

from typing import Any

from src.shared import db
from src.shared.observability import tracer

_SELECT_BY_EMAIL_SHA256 = """
    SELECT id
    FROM patients
    WHERE email_sha256 = %s
"""

_INSERT_PATIENT = """
    INSERT INTO patients
        (first_name, last_name, dob_hash, email_hash, email_sha256, phone_hash)
    VALUES
        (%s, %s, %s, %s, %s, %s)
    RETURNING id, status
"""


@tracer.capture_method
def find_by_email_sha256(email_sha256: str) -> list[dict[str, Any]]:
    """Return matching patient rows for the given email SHA-256 digest."""
    return db.execute_query(_SELECT_BY_EMAIL_SHA256, (email_sha256,))


@tracer.capture_method
def insert_patient(
    first_name: str,
    last_name: str,
    dob_hash: str,
    email_hash: str,
    email_sha256: str,
    phone_hash: str,
) -> dict[str, Any]:
    """Insert a new patient row and return the created id and status."""
    rows = db.execute_query(
        _INSERT_PATIENT,
        (first_name, last_name, dob_hash, email_hash, email_sha256, phone_hash),
        fetch=True,
    )
    return rows[0]
