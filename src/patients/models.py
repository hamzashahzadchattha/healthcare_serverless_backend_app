"""Pydantic v2 models for patient registration input and output."""

from datetime import date

from pydantic import BaseModel, EmailStr, Field, field_validator


class PatientRegistrationRequest(BaseModel):
    """Validated input for POST /patients/register."""

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    dob: date
    email: EmailStr
    phone: str = Field(pattern=r"^\+?[1-9]\d{7,14}$")

    @field_validator("dob")
    @classmethod
    def dob_must_be_past(cls, v: date) -> date:
        if v >= date.today():
            raise ValueError("Date of birth must be in the past")
        return v

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.lower().strip()


class PatientRegistrationResponse(BaseModel):
    """Response payload for a successful patient registration."""

    patient_id: str
    status: str
