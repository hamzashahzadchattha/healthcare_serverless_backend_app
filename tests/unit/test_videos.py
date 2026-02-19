"""Unit tests for GET /patients/{patient_id}/education-videos."""

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_api_event


PATIENT_ID = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def _mock_db_module(mock_db):
    _, mock_conn, mock_cursor = mock_db
    mock_cursor.fetchall.side_effect = [
        [{"id": PATIENT_ID}],
        [{"condition_name": "Type 2 Diabetes", "icd10_code": "E11.9"}],
    ]
    return mock_cursor


@pytest.fixture
def mock_youtube():
    with patch("src.education.videos.youtube_client") as yt_mock:
        yt_mock.search_videos.return_value = [
            {
                "video_id": "abc123",
                "title": "Diabetes Education",
                "description": "Learn about diabetes.",
                "url": "https://www.youtube.com/watch?v=abc123",
            },
        ]
        yield yt_mock


@pytest.fixture
def mock_cache():
    with patch("src.education.videos.cache") as cache_mock:
        cache_mock.make_key.return_value = "sha256hex"
        cache_mock.get.return_value = None
        yield cache_mock


def test_videos_success(_mock_db_module, mock_youtube, mock_cache):
    from src.education.videos import handler

    event = make_api_event(
        path=f"/patients/{PATIENT_ID}/education-videos",
        path_parameters={"patient_id": PATIENT_ID},
    )
    result = handler(event, MagicMock(aws_request_id="req-040"))
    body = json.loads(result["body"])
    assert result["statusCode"] == 200
    assert body["success"] is True
    assert body["data"]["total"] == 1
    assert body["data"]["videos"][0]["video_id"] == "abc123"


def test_videos_no_conditions(_mock_db_module, mock_youtube, mock_cache):
    from src.education.videos import handler

    _mock_db_module.fetchall.side_effect = [
        [{"id": PATIENT_ID}],
        [],
    ]
    event = make_api_event(
        path=f"/patients/{PATIENT_ID}/education-videos",
        path_parameters={"patient_id": PATIENT_ID},
    )
    result = handler(event, MagicMock(aws_request_id="req-041"))
    body = json.loads(result["body"])
    assert result["statusCode"] == 200
    assert body["data"]["total"] == 0
    assert body["data"]["message"] == "No active conditions on file"


def test_videos_patient_not_found(_mock_db_module, mock_youtube, mock_cache):
    from src.education.videos import handler

    _mock_db_module.fetchall.side_effect = [
        [],
    ]
    event = make_api_event(
        path=f"/patients/{PATIENT_ID}/education-videos",
        path_parameters={"patient_id": PATIENT_ID},
    )
    result = handler(event, MagicMock(aws_request_id="req-042"))
    body = json.loads(result["body"])
    assert result["statusCode"] == 404
    assert body["error"]["code"] == "NOT_FOUND"


def test_videos_youtube_error(_mock_db_module, mock_cache):
    from src.education.videos import handler
    from src.shared.exceptions import ExternalServiceError

    with patch("src.education.videos.youtube_client") as yt_mock:
        yt_mock.search_videos.side_effect = ExternalServiceError("YouTube down")
        mock_cache.get.return_value = None

        event = make_api_event(
            path=f"/patients/{PATIENT_ID}/education-videos",
            path_parameters={"patient_id": PATIENT_ID},
        )
        result = handler(event, MagicMock(aws_request_id="req-043"))
        body = json.loads(result["body"])
        assert result["statusCode"] == 502
        assert body["error"]["code"] == "EXTERNAL_SERVICE_ERROR"
