"""YouTube Data API v3 client for patient education video search."""

import os
from typing import Any

import requests

from src.shared.exceptions import ExternalServiceError, RateLimitExceededError
from src.shared.logger import get_logger
from src.shared.secrets import get_secret

_logger = get_logger(__name__)

_YOUTUBE_SECRET_NAME = os.environ.get("YOUTUBE_SECRET_NAME")
_YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_MAX_RESULTS = 5
_REQUEST_TIMEOUT = (3, 6)


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
        Returns an empty list on any external service failure.
    """
    try:
        api_key = _get_api_key()
    except Exception as exc:
        _logger.error("Failed to retrieve YouTube API key", exc_info=True)
        return []

    params = {
        "key": api_key,
        "part": "snippet",
        "type": "video",
        "safeSearch": "strict",
        "relevanceLanguage": "en",
        "maxResults": _MAX_RESULTS,
        "q": topic,
    }

    _logger.info("Calling YouTube search API", topic=topic)

    try:
        resp = requests.get(
            _YOUTUBE_SEARCH_URL,
            params=params,
            timeout=_REQUEST_TIMEOUT,
        )
    except requests.Timeout:
        _logger.warning("YouTube API request timed out", topic=topic)
        return []
    except requests.RequestException as exc:
        _logger.warning("YouTube API request failed", topic=topic, error=str(exc))
        return []

    if resp.status_code == 429:
        _logger.warning("YouTube API quota exceeded", topic=topic)
        return []

    if not resp.ok:
        _logger.warning(
            "YouTube API returned an error",
            http_status=resp.status_code,
            response_body=resp.text[:500],  # cap at 500 chars to avoid log spam
            topic=topic,
        )
        return []

    data = resp.json()
    results: list[dict[str, Any]] = []
    for item in data.get("items", []):
        video_id = item.get("id", {}).get("videoId", "")
        if not video_id:
            continue
        snippet = item.get("snippet", {})
        results.append(
            {
                "video_id": video_id,
                "title": snippet.get("title", ""),
                "description": snippet.get("description", "")[:300],
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail": (snippet.get("thumbnails", {}).get("medium", {}).get("url", "")),
                "channel": snippet.get("channelTitle", ""),
            }
        )

    _logger.info("YouTube search completed", topic=topic, count=len(results))
    return results
