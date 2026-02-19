"""YouTube Data API v3 client for patient education video search."""

import os
from typing import Any

import requests

from src.shared.exceptions import ExternalServiceError, RateLimitExceededError
from src.shared.logger import get_logger
from src.shared.secrets import get_secret


_logger = get_logger(__name__)

_YOUTUBE_SECRET_NAME = os.environ.get("YOUTUBE_SECRET_NAME", "")
_YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_MAX_RESULTS = 5
_REQUEST_TIMEOUT_SECONDS = 10


def _get_api_key() -> str:
    """Retrieve the YouTube API key from Secrets Manager."""
    secret = get_secret(_YOUTUBE_SECRET_NAME)
    return secret["api_key"]


def search_videos(topic: str) -> list[dict[str, Any]]:
    """Search YouTube for educational videos matching the given medical topic.

    Args:
        topic: A medical topic string derived from the patient's condition.

    Returns:
        List of video result dicts with video_id, title, description, and url.

    Raises:
        ExternalServiceError: When the YouTube API returns a non-success response.
        RateLimitExceededError: When YouTube quota is exhausted (HTTP 429).
    """
    api_key = _get_api_key()
    params = {
        "key": api_key,
        "part": "snippet",
        "type": "video",
        "safeSearch": "strict",
        "relevanceLanguage": "en",
        "maxResults": _MAX_RESULTS,
        "q": f"{topic} patient education",
    }

    _logger.info("Calling YouTube search API", topic=topic)

    try:
        resp = requests.get(
            _YOUTUBE_SEARCH_URL,
            params=params,
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        raise ExternalServiceError(
            "YouTube API request timed out",
            details={"topic": topic},
        ) from exc
    except requests.RequestException as exc:
        raise ExternalServiceError(
            "YouTube API request failed",
            details={"topic": topic},
        ) from exc

    if resp.status_code == 429:
        raise RateLimitExceededError("YouTube API quota exceeded")

    if not resp.ok:
        raise ExternalServiceError(
            "YouTube API returned an error",
            details={"http_status": resp.status_code},
        )

    data = resp.json()
    results: list[dict[str, Any]] = []
    for item in data.get("items", []):
        video_id = item.get("id", {}).get("videoId", "")
        snippet = item.get("snippet", {})
        results.append(
            {
                "video_id": video_id,
                "title": snippet.get("title", ""),
                "description": snippet.get("description", "")[:300],
                "url": f"https://www.youtube.com/watch?v={video_id}",
            }
        )

    _logger.info("YouTube search completed", topic=topic, result_count=len(results))
    return results
