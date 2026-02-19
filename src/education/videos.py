"""GET /patients/{patient_id}/education-videos — returns curated YouTube video recommendations."""

import time
from typing import Any

from src.education import cache, youtube_client
from src.shared import db, response
from src.shared.exceptions import HealthcarePlatformError, RecordNotFoundError
from src.shared.logger import get_logger
from src.shared.request_validator import validate_uuid_path_param


_logger = get_logger(__name__)

_CHECK_PATIENT_EXISTS = "SELECT id FROM patients WHERE id = %s AND status = 'active'"

_SELECT_ACTIVE_CONDITIONS = """
    SELECT DISTINCT condition_name, icd10_code
    FROM patient_conditions
    WHERE patient_id = %s AND status IN ('active', 'chronic')
"""

_MAX_TOTAL_VIDEOS = 10


def _get_topic_label(condition_name: str, icd10_code: str | None) -> str:
    """Return the search topic string for a condition.

    ICD-10 codes are more precise search terms when available.
    """
    if icd10_code:
        return f"{icd10_code} {condition_name}"
    return condition_name


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for GET /patients/{patient_id}/education-videos."""
    _logger.set_request_id(context.aws_request_id)
    start = time.perf_counter()

    path_params = event.get("pathParameters") or {}
    _logger.info("Education videos request received")

    try:
        patient_id = validate_uuid_path_param(path_params.get("patient_id"), "patient_id")

        patient_rows = db.execute_query(_CHECK_PATIENT_EXISTS, (patient_id,))
        if not patient_rows:
            raise RecordNotFoundError("Patient not found")

        condition_rows = db.execute_query(_SELECT_ACTIVE_CONDITIONS, (patient_id,))
        if not condition_rows:
            _logger.info("No active conditions found for patient", patient_id=patient_id)
            return response.success(
                data={"videos": [], "message": "No active conditions on file", "total": 0},
            )

        all_videos: list[dict[str, Any]] = []
        seen_video_ids: set[str] = set()

        for condition in condition_rows:
            if len(all_videos) >= _MAX_TOTAL_VIDEOS:
                break

            topic = _get_topic_label(
                condition["condition_name"],
                condition.get("icd10_code"),
            )
            cache_key = cache.make_key(topic)
            cached = cache.get(cache_key)

            if cached is not None:
                _logger.debug("Cache hit for education videos", cache_key=cache_key)
                videos = cached
            else:
                _logger.debug("Cache miss for education videos", cache_key=cache_key)
                videos = youtube_client.search_videos(topic)
                cache.put(cache_key, videos)

            for video in videos:
                if video["video_id"] not in seen_video_ids:
                    seen_video_ids.add(video["video_id"])
                    all_videos.append({**video, "topic": condition["condition_name"]})

        capped_videos = all_videos[:_MAX_TOTAL_VIDEOS]
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.info(
            "Education videos retrieved",
            patient_id=patient_id,
            conditions_queried=len(condition_rows),
            video_count=len(capped_videos),
            duration_ms=elapsed_ms,
        )

        return response.success(
            data={"videos": capped_videos, "total": len(capped_videos)},
        )

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.warning(
            "Education videos request failed",
            error_code=exc.error_code,
            duration_ms=elapsed_ms,
        )
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.error(
            "Unexpected error fetching education videos",
            duration_ms=elapsed_ms,
        )
        return response.error(
            message="An unexpected error occurred",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )
