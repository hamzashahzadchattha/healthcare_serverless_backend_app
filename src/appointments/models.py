"""Pydantic v2 models for appointment endpoints."""

from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ProviderNoteRequest(BaseModel):
    """Validated input for POST /appointments/{appointment_id}/notes."""

    provider_id: str
    note_text: str = Field(min_length=1, max_length=10_000)

    @field_validator("provider_id", mode="before")
    @classmethod
    def validate_uuid(cls, v: str | UUID) -> str:
        """Accept UUID objects or strings, normalise to lowercase string."""
        return str(v).lower()
