"""Unit tests for education videos -- tests service and handler separately."""

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_api_event


PATIENT_ID = str(uuid.uuid4())

MOCK_CONDITION_ROW = {"condition_name": "Type 2 Diabetes", "icd10_code": "E11.9"}

MOCK_VIDEO = {
    "video_id": "abc123",
    "title": "Diabetes Education",
    "description": "Learn about diabetes.",
    "url": "https://www.youtube.com/watch?v=abc123",
}


class TestEducationService:
    """Tests for src/education/service.py -- no HTTP mocking."""

    def test_patient_not_found_raises_error(self):
        from src.education import service
        from src.shared.exceptions import RecordNotFoundError

        with patch("src.education.service.repository.patient_exists", return_value=False):
            with pytest.raises(RecordNotFoundError):
                service.get_education_videos(PATIENT_ID)

    def test_no_conditions_returns_empty(self):
        from src.education import service

        with patch("src.education.service.repository.patient_exists", return_value=True):
            with patch(
                "src.education.service.repository.get_active_conditions",
                return_value=[],
            ):
                result = service.get_education_videos(PATIENT_ID)
                assert result["total"] == 0
                assert result["videos"] == []
                assert "No active conditions" in result["message"]

    def test_success_returns_videos(self):
        from src.education import service

        with patch("src.education.service.repository.patient_exists", return_value=True):
            with patch(
                "src.education.service.repository.get_active_conditions",
                return_value=[MOCK_CONDITION_ROW],
            ):
                with patch("src.education.service.cache") as mock_cache:
                    mock_cache.make_key.return_value = "sha256hex"
                    mock_cache.get.return_value = None
                    with patch("src.education.service.youtube_client") as mock_yt:
                        mock_yt.search_videos.return_value = [MOCK_VIDEO]
                        result = service.get_education_videos(PATIENT_ID)
                        assert result["total"] == 1
                        assert result["videos"][0]["video_id"] == "abc123"
                        assert result["videos"][0]["topic"] == "Type 2 Diabetes"
                        mock_cache.set.assert_called_once()


class TestEducationHandler:
    """Tests for src/education/handler.py -- full event-to-response flow."""

    def test_success_returns_200(self):
        from src.education.handler import handler

        with patch("src.education.service.repository.patient_exists", return_value=True):
            with patch(
                "src.education.service.repository.get_active_conditions",
                return_value=[MOCK_CONDITION_ROW],
            ):
                with patch("src.education.service.cache") as mock_cache:
                    mock_cache.make_key.return_value = "sha256hex"
                    mock_cache.get.return_value = None
                    with patch("src.education.service.youtube_client") as mock_yt:
                        mock_yt.search_videos.return_value = [MOCK_VIDEO]
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

    def test_no_conditions_returns_200_empty(self):
        from src.education.handler import handler

        with patch("src.education.service.repository.patient_exists", return_value=True):
            with patch(
                "src.education.service.repository.get_active_conditions",
                return_value=[],
            ):
                event = make_api_event(
                    path=f"/patients/{PATIENT_ID}/education-videos",
                    path_parameters={"patient_id": PATIENT_ID},
                )
                result = handler(event, MagicMock(aws_request_id="req-041"))
                body = json.loads(result["body"])
                assert result["statusCode"] == 200
                assert body["data"]["total"] == 0

    def test_patient_not_found_returns_404(self):
        from src.education.handler import handler

        with patch("src.education.service.repository.patient_exists", return_value=False):
            event = make_api_event(
                path=f"/patients/{PATIENT_ID}/education-videos",
                path_parameters={"patient_id": PATIENT_ID},
            )
            result = handler(event, MagicMock(aws_request_id="req-042"))
            body = json.loads(result["body"])
            assert result["statusCode"] == 404
            assert body["error"]["code"] == "NOT_FOUND"

    def test_youtube_error_returns_502(self):
        from src.education.handler import handler
        from src.shared.exceptions import ExternalServiceError

        with patch("src.education.service.repository.patient_exists", return_value=True):
            with patch(
                "src.education.service.repository.get_active_conditions",
                return_value=[MOCK_CONDITION_ROW],
            ):
                with patch("src.education.service.cache") as mock_cache:
                    mock_cache.make_key.return_value = "sha256hex"
                    mock_cache.get.return_value = None
                    with patch("src.education.service.youtube_client") as mock_yt:
                        mock_yt.search_videos.side_effect = ExternalServiceError("YouTube down")
                        event = make_api_event(
                            path=f"/patients/{PATIENT_ID}/education-videos",
                            path_parameters={"patient_id": PATIENT_ID},
                        )
                        result = handler(event, MagicMock(aws_request_id="req-043"))
                        body = json.loads(result["body"])
                        assert result["statusCode"] == 502
                        assert body["error"]["code"] == "EXTERNAL_SERVICE_ERROR"

    def test_unexpected_exception_returns_500(self):
        from src.education.handler import handler

        with patch(
            "src.education.service.repository.patient_exists",
            side_effect=Exception("DB down"),
        ):
            event = make_api_event(
                path=f"/patients/{PATIENT_ID}/education-videos",
                path_parameters={"patient_id": PATIENT_ID},
            )
            result = handler(event, MagicMock(aws_request_id="req-044"))
            body = json.loads(result["body"])
            assert result["statusCode"] == 500
            assert body["success"] is False
