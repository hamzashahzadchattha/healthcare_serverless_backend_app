"""Pure Python dataclass models for patient registration — no Pydantic dependency.

Used by the benchmark variant to measure cold-start and runtime cost of
stdlib-only validation vs Pydantic v2.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)
_PHONE_RE = re.compile(r"^\+?[1-9]\d{7,14}$")


@dataclass(frozen=True, slots=True)
class PatientRegistrationRequest:
    """Validated input for POST /patients/register-dc."""

    first_name: str
    last_name: str
    dob: date
    email: str
    phone: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PatientRegistrationRequest":
        """Parse and validate a raw request body dict.

        Raises:
            ValueError: With a list of field error strings on any validation failure.
        """
        errors: list[str] = []

        first_name = data.get("first_name", "")
        if not isinstance(first_name, str) or not 1 <= len(first_name) <= 100:
            errors.append("Field 'first_name': must be a string between 1 and 100 characters")

        last_name = data.get("last_name", "")
        if not isinstance(last_name, str) or not 1 <= len(last_name) <= 100:
            errors.append("Field 'last_name': must be a string between 1 and 100 characters")

        dob_raw = data.get("dob", "")
        dob: date | None = None
        if not isinstance(dob_raw, str):
            errors.append("Field 'dob': must be a string in YYYY-MM-DD format")
        else:
            try:
                dob = datetime.strptime(dob_raw, "%Y-%m-%d").date()
                if dob >= date.today():
                    errors.append("Field 'dob': date of birth must be in the past")
            except ValueError:
                errors.append("Field 'dob': must be a valid date in YYYY-MM-DD format")

        email_raw = data.get("email", "")
        if not isinstance(email_raw, str):
            errors.append("Field 'email': must be a string")
            email_raw = ""
        email = email_raw.lower().strip()
        if not email or len(email) > 254 or not _EMAIL_RE.match(email):
            errors.append("Field 'email': must be a valid email address (max 254 chars)")

        phone = data.get("phone", "")
        if not isinstance(phone, str) or not _PHONE_RE.match(phone):
            errors.append("Field 'phone': must be E.164 format e.g. +12025551234")

        if errors:
            raise ValueError(errors)

        return cls(
            first_name=first_name,
            last_name=last_name,
            dob=dob,  # type: ignore[arg-type]
            email=email,
            phone=phone,
        )


@dataclass(frozen=True, slots=True)
class PatientRegistrationResponse:
    """Response payload for a successful patient registration."""

    patient_id: str
    status: str

    def to_dict(self) -> dict[str, str]:
        """Serialise to a plain dict for the response builder."""
        return {"patient_id": self.patient_id, "status": self.status}
