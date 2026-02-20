"""Unit tests for src/shared/validators.py -- all 4 parse functions."""

import json

import pytest
from pydantic import BaseModel, Field

from src.shared.exceptions import ValidationError
from src.shared.validators import (
    parse_body,
    parse_enum_param,
    parse_int_param,
    parse_uuid_param,
)

# ── Minimal Pydantic model used only in these tests ────────────────────── #


class _SampleModel(BaseModel):
    name: str = Field(min_length=1)
    age: int


# ── parse_body ─────────────────────────────────────────────────────────── #


class TestParseBody:
    def test_none_body_raises(self):
        with pytest.raises(ValidationError, match="Request body is required"):
            parse_body(None, _SampleModel)

    def test_empty_string_raises(self):
        with pytest.raises(ValidationError, match="Request body is required"):
            parse_body("", _SampleModel)

    def test_invalid_json_raises(self):
        with pytest.raises(ValidationError, match="valid JSON"):
            parse_body("{bad json", _SampleModel)

    def test_pydantic_validation_failure_includes_field_errors(self):
        body = json.dumps({"name": "", "age": "not_int"})
        with pytest.raises(ValidationError) as exc_info:
            parse_body(body, _SampleModel)
        assert "field_errors" in exc_info.value.details

    def test_missing_required_field_raises(self):
        body = json.dumps({"name": "Alice"})
        with pytest.raises(ValidationError, match="validation failed"):
            parse_body(body, _SampleModel)

    def test_valid_body_returns_model(self):
        body = json.dumps({"name": "Alice", "age": 30})
        result = parse_body(body, _SampleModel)
        assert isinstance(result, _SampleModel)
        assert result.name == "Alice"
        assert result.age == 30


# ── parse_uuid_param ──────────────────────────────────────────────────── #


class TestParseUuidParam:
    def test_none_raises(self):
        with pytest.raises(ValidationError, match="is required"):
            parse_uuid_param(None, "patient_id")

    def test_empty_string_raises(self):
        with pytest.raises(ValidationError, match="is required"):
            parse_uuid_param("", "patient_id")

    def test_invalid_format_raises(self):
        with pytest.raises(ValidationError, match="valid UUID"):
            parse_uuid_param("not-a-uuid", "patient_id")

    def test_short_hex_raises(self):
        with pytest.raises(ValidationError, match="valid UUID"):
            parse_uuid_param("12345678-1234-1234-1234", "patient_id")

    def test_valid_uuid_lowercase(self):
        uuid_str = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        assert parse_uuid_param(uuid_str, "id") == uuid_str

    def test_uppercase_normalised_to_lowercase(self):
        uuid_upper = "A1B2C3D4-E5F6-7890-ABCD-EF1234567890"
        assert parse_uuid_param(uuid_upper, "id") == uuid_upper.lower()


# ── parse_enum_param ──────────────────────────────────────────────────── #


ALLOWED = ["active", "past", "all"]


class TestParseEnumParam:
    def test_none_returns_default(self):
        assert parse_enum_param(None, "filter", ALLOWED, default="active") == "active"

    def test_none_returns_none_when_no_default(self):
        assert parse_enum_param(None, "filter", ALLOWED) is None

    def test_valid_value_passes(self):
        assert parse_enum_param("past", "filter", ALLOWED) == "past"

    def test_invalid_value_raises(self):
        with pytest.raises(ValidationError, match="must be one of"):
            parse_enum_param("invalid", "filter", ALLOWED)


# ── parse_int_param ───────────────────────────────────────────────────── #


class TestParseIntParam:
    def test_none_returns_default(self):
        assert parse_int_param(None, "page", default=1) == 1

    def test_valid_integer_string(self):
        assert parse_int_param("5", "page", default=1) == 5

    def test_non_integer_raises(self):
        with pytest.raises(ValidationError, match="must be an integer"):
            parse_int_param("abc", "page", default=1)

    def test_float_string_raises(self):
        with pytest.raises(ValidationError, match="must be an integer"):
            parse_int_param("3.5", "page", default=1)

    def test_below_min_raises(self):
        with pytest.raises(ValidationError, match="at least"):
            parse_int_param("0", "page", default=1, min_value=1)

    def test_above_max_raises(self):
        with pytest.raises(ValidationError, match="at most"):
            parse_int_param("200", "limit", default=50, max_value=100)

    def test_exactly_min_passes(self):
        assert parse_int_param("1", "page", default=1, min_value=1) == 1

    def test_exactly_max_passes(self):
        assert parse_int_param("100", "limit", default=50, max_value=100) == 100

    def test_negative_value_allowed_when_no_min(self):
        assert parse_int_param("-5", "offset", default=0) == -5
