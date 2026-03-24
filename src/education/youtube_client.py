"""YouTube Data API v3 client for patient education video search."""

import os
from typing import Any

import requests

from src.shared.exceptions import ExternalServiceError, RateLimitExceededError  # noqa: F401 – kept for API surface
from src.shared.observability import logger, tracer
from src.shared.parameters import get_youtube_api_key

_YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_MAX_RESULTS = 5
_REQUEST_TIMEOUT = (3, 6)


@tracer.capture_method
def search_videos(topic: str) -> list[dict[str, Any]]:
    """Search YouTube for educational videos matching the given medical topic.

    Args:
        topic: A medical topic string derived from the patient's condition.

    Returns:
        List of video result dicts with video_id, title, description, and url.
        Returns an empty list on any external service failure.
    """
    try:
        api_key = get_youtube_api_key()
    except Exception:
        logger.exception("Failed to retrieve YouTube API key")
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

    logger.info("Calling YouTube search API", extra={"result_count": _MAX_RESULTS})

    try:
        resp = requests.get(
            _YOUTUBE_SEARCH_URL,
            params=params,
            timeout=_REQUEST_TIMEOUT,
        )
    except requests.Timeout:
        logger.warning("YouTube API request timed out")
        return []
    except requests.RequestException as exc:
        logger.warning("YouTube API request failed", extra={"error": str(exc)})
        return []

    if resp.status_code == 429:
        logger.warning("YouTube API quota exceeded")
        return []

    if not resp.ok:
        logger.warning(
            "YouTube API returned an error",
            extra={"http_status": resp.status_code, "response_body": resp.text[:500]},
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

    logger.info("YouTube search completed", extra={"count": len(results)})
    return results
