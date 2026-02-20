"""Type definitions for prescription endpoints."""

from typing import Literal


PrescriptionFilter = Literal["active", "past", "all"]

PRESCRIPTION_FILTER_VALUES: list[str] = ["active", "past", "all"]
