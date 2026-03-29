"""Pydantic response models for the admin patient management API."""

from datetime import datetime

from pydantic import BaseModel


class PatientListResponse(BaseModel):
    patient_id: str
    first_name: str
    last_name: str
    status: str
    created_at: datetime
    cognito_sub: str | None


class PatientDetailResponse(PatientListResponse):
    updated_at: datetime
