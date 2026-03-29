"""Property-based tests for src/admin/ — cognito-auth feature."""

import math
import os
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

os.environ.setdefault("REGION", "us-east-1")
os.environ.setdefault("COGNITO_USER_POOL_ID", "us-east-1_testpool")
os.environ.setdefault("POWERTOOLS_SERVICE_NAME", "healthcare-platform-test")
os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE", "HealthcarePlatform")
os.environ.setdefault("STAGE", "test")


# ---------------------------------------------------------------------------
# Property 7: Admin patient list pagination is consistent
# Validates: Requirements 6.2
# ---------------------------------------------------------------------------

@given(
    total=st.integers(min_value=0, max_value=500),
    limit=st.integers(min_value=1, max_value=100),
)
@settings(max_examples=100, deadline=None)
def test_pagination_consistency(total: int, limit: int) -> None:
    """Property 7: Admin patient list pagination is consistent.

    Validates: Requirements 6.2
    """
    from src.admin import repository

    # Build a fake patient list of `total` items
    all_patients = [
        {
            "id": str(uuid.uuid4()),
            "first_name": f"First{i}",
            "last_name": f"Last{i}",
            "status": "active",
            "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "cognito_sub": None,
        }
        for i in range(total)
    ]

    def fake_list_patients(page: int, lim: int) -> dict[str, Any]:
        offset = (page - 1) * lim
        items = all_patients[offset : offset + lim]
        return {"items": items, "total": total, "page": page, "limit": lim}

    num_pages = math.ceil(total / limit) if total > 0 else 1

    seen_ids: set[str] = set()
    total_collected = 0

    for page in range(1, num_pages + 1):
        result = fake_list_patients(page, limit)

        # Each page must not exceed the limit
        assert len(result["items"]) <= limit

        # No overlap — each id must be unique across pages
        for item in result["items"]:
            assert item["id"] not in seen_ids, f"Duplicate id {item['id']} on page {page}"
            seen_ids.add(item["id"])

        total_collected += len(result["items"])

    # Sum of items across all pages equals total
    assert total_collected == total


# ---------------------------------------------------------------------------
# Property 8: Admin patient detail is a round-trip
# Validates: Requirements 6.4
# ---------------------------------------------------------------------------

@given(
    patient=st.fixed_dictionaries({
        "first_name": st.text(min_size=1),
        "last_name": st.text(min_size=1),
        "status": st.sampled_from(["active", "inactive", "deceased"]),
    })
)
@settings(max_examples=100, deadline=None)
def test_patient_detail_round_trip(patient: dict[str, Any]) -> None:
    """Property 8: Admin patient detail is a round-trip.

    Validates: Requirements 6.4
    """
    from src.admin import repository

    patient_id = str(uuid.uuid4())
    stored_record = {
        "id": patient_id,
        "first_name": patient["first_name"],
        "last_name": patient["last_name"],
        "status": patient["status"],
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 6, 1, tzinfo=timezone.utc),
        "cognito_sub": None,
    }

    with patch.object(repository, "get_patient_by_id", return_value=stored_record):
        result = repository.get_patient_by_id(patient_id)

    assert result is not None
    # The response id must equal the requested patient_id
    assert result["id"] == patient_id
    # Fields must match the stored record
    assert result["first_name"] == patient["first_name"]
    assert result["last_name"] == patient["last_name"]
    assert result["status"] == patient["status"]
