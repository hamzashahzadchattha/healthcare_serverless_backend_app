"""Property-based tests for src/shared/auth.py — cognito-auth feature."""

import json
import os
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

os.environ.setdefault("REGION", "us-east-1")
os.environ.setdefault("COGNITO_USER_POOL_ID", "us-east-1_testpool")

import src.shared.auth as auth_module
from src.shared.auth import require_admin, require_auth
from src.shared.exceptions import ForbiddenError, UnauthorizedError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(header_name: str, header_value: str) -> dict[str, Any]:
    return {
        "headers": {header_name: header_value},
        "requestContext": {},
    }


def _make_event_no_auth() -> dict[str, Any]:
    return {"headers": {}, "requestContext": {}}


def _dummy_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    return {"statusCode": 200}


# ---------------------------------------------------------------------------
# Property 1: Authorization header extraction is case-insensitive
# Validates: Requirements 2.2
# ---------------------------------------------------------------------------

@given(header_name=st.sampled_from(["authorization", "Authorization", "AUTHORIZATION", "aUtHoRiZaTiOn"]))
@settings(max_examples=100)
def test_header_extraction_case_insensitive(header_name: str) -> None:
    """Property 1: Authorization header extraction is case-insensitive."""
    fake_claims = {"sub": str(uuid.uuid4()), "cognito:groups": []}
    fake_kid = "test-kid"
    fake_jwk = {"kid": fake_kid, "kty": "RSA"}
    fake_token = "fake.jwt.token"
    fake_public_key = MagicMock()

    event = _make_event(header_name, f"Bearer {fake_token}")

    with patch.object(auth_module, "_jwks_cache", {fake_kid: fake_jwk}):
        with patch("jwt.get_unverified_header", return_value={"kid": fake_kid}):
            with patch("jwt.algorithms.RSAAlgorithm.from_jwk", return_value=fake_public_key):
                with patch("jwt.decode", return_value=fake_claims):
                    decorated = require_auth(_dummy_handler)
                    try:
                        result = decorated(event, None)
                        assert result["statusCode"] == 200
                    except UnauthorizedError:
                        pytest.fail(f"UnauthorizedError raised for header name: {header_name!r}")


# ---------------------------------------------------------------------------
# Property 2: Missing or malformed Authorization header raises UnauthorizedError
# Validates: Requirements 2.3
# ---------------------------------------------------------------------------

@given(bad_header=st.one_of(st.none(), st.text().filter(lambda s: not s.startswith("Bearer "))))
@settings(max_examples=100)
def test_missing_or_malformed_header_raises_unauthorized(bad_header: str | None) -> None:
    """Property 2: Missing or malformed Authorization header raises UnauthorizedError."""
    if bad_header is None:
        event: dict[str, Any] = {"headers": {}, "requestContext": {}}
    else:
        event = _make_event("Authorization", bad_header)

    decorated = require_auth(_dummy_handler)
    with pytest.raises(UnauthorizedError) as exc_info:
        decorated(event, None)

    assert str(exc_info.value) == "Authorization header missing or malformed"


# ---------------------------------------------------------------------------
# Property 3: Valid JWT claims are injected into the event
# Validates: Requirements 2.4, 2.9
# ---------------------------------------------------------------------------

@given(
    claims=st.fixed_dictionaries(
        {"sub": st.uuids().map(str), "cognito:groups": st.lists(st.text())}
    )
)
@settings(max_examples=100)
def test_valid_jwt_injects_claims(claims: dict[str, Any]) -> None:
    """Property 3: Valid JWT claims are injected into the event."""
    fake_kid = "test-kid"
    fake_jwk = {"kid": fake_kid, "kty": "RSA"}
    fake_token = "fake.jwt.token"
    fake_public_key = MagicMock()

    captured_event: dict[str, Any] = {}

    def capturing_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
        captured_event.update(event)
        return {"statusCode": 200}

    event = _make_event("Authorization", f"Bearer {fake_token}")

    with patch.object(auth_module, "_jwks_cache", {fake_kid: fake_jwk}):
        with patch("jwt.get_unverified_header", return_value={"kid": fake_kid}):
            with patch("jwt.algorithms.RSAAlgorithm.from_jwk", return_value=fake_public_key):
                with patch("jwt.decode", return_value=claims):
                    decorated = require_auth(capturing_handler)
                    decorated(event, None)

    injected = captured_event["requestContext"]["authorizer"]["claims"]
    assert injected["sub"] == claims["sub"]


# ---------------------------------------------------------------------------
# Property 4: JWKS endpoint is fetched at most once per unique key set
# Validates: Requirements 2.5
# ---------------------------------------------------------------------------

@given(n_invocations=st.integers(min_value=2, max_value=20))
@settings(max_examples=100)
def test_jwks_fetched_once_per_kid(n_invocations: int) -> None:
    """Property 4: JWKS endpoint is fetched at most once per unique key set."""
    fake_kid = "shared-kid"
    fake_jwk = {"kid": fake_kid, "kty": "RSA"}
    fake_claims = {"sub": str(uuid.uuid4()), "cognito:groups": []}
    fake_token = "fake.jwt.token"
    fake_public_key = MagicMock()

    mock_response = MagicMock()
    mock_response.json.return_value = {"keys": [fake_jwk]}
    mock_response.raise_for_status = MagicMock()

    # Save and restore the real cache around the test
    original_cache = auth_module._jwks_cache.copy()
    auth_module._jwks_cache.clear()

    try:
        with patch("requests.get", return_value=mock_response) as mock_get:
            with patch("jwt.get_unverified_header", return_value={"kid": fake_kid}):
                with patch("jwt.algorithms.RSAAlgorithm.from_jwk", return_value=fake_public_key):
                    with patch("jwt.decode", return_value=fake_claims):
                        decorated = require_auth(_dummy_handler)
                        for _ in range(n_invocations):
                            event = _make_event("Authorization", f"Bearer {fake_token}")
                            decorated(event, None)

        assert mock_get.call_count == 1, (
            f"Expected 1 JWKS fetch but got {mock_get.call_count} for {n_invocations} invocations"
        )
    finally:
        auth_module._jwks_cache.clear()
        auth_module._jwks_cache.update(original_cache)


# ---------------------------------------------------------------------------
# Property 5: Admin access is granted iff cognito:groups contains "admin"
# Validates: Requirements 3.3, 3.4
# ---------------------------------------------------------------------------

@given(groups=st.lists(st.text()))
@settings(max_examples=100)
def test_admin_access_iff_admin_group(groups: list[str]) -> None:
    """Property 5: Admin access is granted iff cognito:groups contains "admin"."""
    fake_kid = "test-kid"
    fake_jwk = {"kid": fake_kid, "kty": "RSA"}
    fake_claims = {"sub": str(uuid.uuid4()), "cognito:groups": groups}
    fake_token = "fake.jwt.token"
    fake_public_key = MagicMock()

    handler_called = False

    def tracking_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
        nonlocal handler_called
        handler_called = True
        return {"statusCode": 200}

    event = _make_event("Authorization", f"Bearer {fake_token}")

    with patch.object(auth_module, "_jwks_cache", {fake_kid: fake_jwk}):
        with patch("jwt.get_unverified_header", return_value={"kid": fake_kid}):
            with patch("jwt.algorithms.RSAAlgorithm.from_jwk", return_value=fake_public_key):
                with patch("jwt.decode", return_value=fake_claims):
                    decorated = require_admin(tracking_handler)
                    if "admin" in groups:
                        result = decorated(event, None)
                        assert handler_called, "Handler should have been called for admin user"
                        assert result["statusCode"] == 200
                    else:
                        with pytest.raises(ForbiddenError) as exc_info:
                            decorated(event, None)
                        assert str(exc_info.value) == "Admin access required"
                        assert not handler_called, "Handler should not be called for non-admin user"


# ---------------------------------------------------------------------------
# Property 6: Patient ownership check grants access iff sub matches or caller is admin
# Validates: Requirements 5.1, 5.2, 5.3, 5.4
# ---------------------------------------------------------------------------

@given(
    caller_sub=st.uuids().map(str),
    patient_sub=st.one_of(st.none(), st.uuids().map(str)),
    is_admin_caller=st.booleans(),
)
@settings(max_examples=200)
def test_patient_ownership_access_control(
    caller_sub: str,
    patient_sub: str | None,
    is_admin_caller: bool,
) -> None:
    """Property 6: Patient ownership check grants access iff sub matches or caller is admin."""
    from src.shared.auth import assert_patient_access

    groups = ["admin"] if is_admin_caller else []
    claims = {"sub": caller_sub, "cognito:groups": groups}

    should_allow = is_admin_caller or (patient_sub is not None and caller_sub == patient_sub)

    if should_allow:
        # Must not raise
        assert_patient_access(claims, patient_sub)
    else:
        with pytest.raises(ForbiddenError) as exc_info:
            assert_patient_access(claims, patient_sub)
        assert str(exc_info.value) == "Access to this patient record is not permitted"
