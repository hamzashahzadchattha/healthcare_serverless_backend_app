"""Business logic for patient education video recommendations.

Orchestrates: patient validation, condition fetch, cache check, YouTube API, dedup.
Does not know about HTTP events or SQL.
"""

from typing import Any

from src.education import cache, repository, youtube_client
from src.shared.exceptions import RecordNotFoundError
from src.shared.observability import logger, metrics, tracer
from aws_lambda_powertools.metrics import MetricUnit

_MAX_VIDEOS = 10


def _topic_label(condition_name: str, icd10_code: str | None) -> str:
    """Derive a YouTube search query from a patient condition.

    ICD-10 codes produce more clinically precise results when available.
    """
    if icd10_code:
        return f"{icd10_code} {condition_name} patient education"
    return f"{condition_name} patient education"


@tracer.capture_method
def get_education_videos(patient_id: str) -> dict[str, Any]:
    """Fetch, cache, and return YouTube videos for a patient's active conditions.

    Args:
        patient_id: Validated UUID string.

    Returns:
        Dict with 'items' list, 'total' count, and metadata.

    Raises:
        RecordNotFoundError: When the patient does not exist.
    """
    rows = repository.get_active_conditions(patient_id)
    if not rows:
        raise RecordNotFoundError("Patient not found")

    # Filter sentinel row produced when patient exists but has no active conditions
    conditions = [r for r in rows if r["condition_name"] is not None]
    if not conditions:
        logger.info("No active conditions for patient", extra={"patient_id": patient_id})
        return {
            "items": [],
            "total": 0,
            "message": "No active conditions on file",
            "conditions_searched": 0,
            "cognito_sub": rows[0].get("cognito_sub"),
        }

    all_videos: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    conditions_searched = 0

    for condition in conditions:
        if len(all_videos) >= _MAX_VIDEOS:
            break

        topic = _topic_label(condition["condition_name"], condition.get("icd10_code"))
        cache_key = cache.make_key(topic)
        cached = cache.get(cache_key)

        if cached is not None:
            logger.debug("Cache hit", extra={"cache_key": cache_key})
            metrics.add_metric(name="CacheHit", unit=MetricUnit.Count, value=1)
            videos = cached
        else:
            logger.debug("Cache miss — calling YouTube", extra={"cache_key": cache_key})
            metrics.add_metric(name="CacheMiss", unit=MetricUnit.Count, value=1)
            # youtube_client.search_videos never raises — returns [] on any failure
            videos = youtube_client.search_videos(topic)
            if videos:
                cache.set(cache_key, videos)

        conditions_searched += 1

        for video in videos:
            if video["video_id"] not in seen_ids:
                seen_ids.add(video["video_id"])
                all_videos.append({**video, "topic": condition["condition_name"]})

    result = all_videos[:_MAX_VIDEOS]
    logger.info(
        "Education videos ready",
        extra={"patient_id": patient_id, "count": len(result), "conditions_searched": conditions_searched},
    )
    return {
        "items": result,
        "total": len(result),
        "conditions_searched": conditions_searched,
        "cognito_sub": rows[0].get("cognito_sub"),
    }
