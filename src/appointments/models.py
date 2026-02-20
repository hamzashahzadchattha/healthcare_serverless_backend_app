"""Pydantic v2 models for appointment endpoints."""

import re
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class ProviderNoteRequest(BaseModel):
    """Validated input for POST /appointments/{appointment_id}/notes."""

    provider_id: str
    note_text: str = Field(min_length=1, max_length=10_000)

    @field_validator("provider_id", mode="before")
    @classmethod
    def validate_uuid(cls, v: str | UUID) -> str:
        """Accept UUID objects or strings, validate format, normalise to lowercase."""
        val = str(v).lower()
        if not _UUID_RE.match(val):
            raise ValueError("provider_id must be a valid UUID")
        return val

    @field_validator("note_text")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        """Reject whitespace-only note text."""
        if not v.strip():
            raise ValueError("Note text cannot be blank")
        return v
