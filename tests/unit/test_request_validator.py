"""Tests for input schema validation."""

import json

import pytest

from src.shared.exceptions import ValidationError
from src.shared.request_validator import (
    validate_body,
    validate_query_param_enum,
    validate_uuid_path_param,
)


_TEST_SCHEMA = {
    "type": "object",
    "required": ["name"],
    "properties": {"name": {"type": "string", "minLength": 1}},
}


def test_validate_body_success():
    result = validate_body(json.dumps({"name": "test"}), _TEST_SCHEMA)
    assert result["name"] == "test"


def test_validate_body_missing():
    with pytest.raises(ValidationError, match="Request body is required"):
        validate_body(None, _TEST_SCHEMA)


def test_validate_body_invalid_json():
    with pytest.raises(ValidationError, match="valid JSON"):
        validate_body("{bad", _TEST_SCHEMA)


def test_validate_body_schema_failure():
    with pytest.raises(ValidationError, match="validation failed"):
        validate_body(json.dumps({"name": ""}), _TEST_SCHEMA)


def test_validate_uuid_path_param_success():
    result = validate_uuid_path_param("A1B2C3D4-0001-4000-8000-000000000001", "id")
    assert result == "a1b2c3d4-0001-4000-8000-000000000001"


def test_validate_uuid_path_param_missing():
    with pytest.raises(ValidationError, match="required"):
        validate_uuid_path_param(None, "id")


def test_validate_uuid_path_param_invalid():
    with pytest.raises(ValidationError, match="valid UUID"):
        validate_uuid_path_param("not-a-uuid", "id")


def test_validate_query_param_enum_valid():
    assert validate_query_param_enum("active", "filter", ["active", "past"]) == "active"


def test_validate_query_param_enum_default():
    assert (
        validate_query_param_enum(None, "filter", ["active", "past"], default="active") == "active"
    )


def test_validate_query_param_enum_invalid():
    with pytest.raises(ValidationError, match="must be one of"):
        validate_query_param_enum("invalid", "filter", ["active", "past"])
