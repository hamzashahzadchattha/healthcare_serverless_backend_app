"""PHI-safe, CloudWatch Logs Insights-compatible structured logger.

Every log line is a flat JSON object. All fields are top-level keys so
CloudWatch Logs Insights can index and filter them without nested traversal.
PHI is scrubbed by both key name and value pattern before any log entry is written.
"""

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any


# ── PHI protection constants ──────────────────────────────────────────────── #

PHI_BLOCKED_KEYS: frozenset[str] = frozenset(
    {
        "email",
        "phone",
        "dob",
        "date_of_birth",
        "birth_date",
        "first_name",
        "last_name",
        "full_name",
        "name",
        "address",
        "street",
        "city",
        "zip",
        "postal_code",
        "ssn",
        "social_security",
        "note_text",
        "notes",
        "medication_name",
        "medication",
        "dosage",
        "dose",
        "diagnosis",
        "icd10_code",
        "icd_code",
        "condition_name",
        "condition",
        "password",
        "secret",
        "token",
        "api_key",
        "key",
        "credential",
        "auth",
        "authorization",
        # "topic" is built from condition_name + icd10_code in the education module
        "topic",
    }
)

_PHI_VALUE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE),
    re.compile(r"^\+?[1-9]\d{7,14}$"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
]

_REDACTED = "[REDACTED]"

# ── Service metadata resolved once at module load ─────────────────────────── #

_SERVICE_NAME: str = os.environ.get("SERVICE_NAME", "healthcare-platform")
_STAGE: str = os.environ.get("STAGE", "dev")
_FUNCTION_NAME: str = os.environ.get("FUNCTION_NAME", "unknown")
_LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").upper()
_LEVEL_INT: int = getattr(logging, _LOG_LEVEL, logging.INFO)


def _scrub_value(value: Any) -> Any:
    """Return value with PHI removed. Recurses into dicts and lists.

    String values are checked against PHI patterns and replaced with [REDACTED]
    if any pattern matches.
    """
    if isinstance(value, str):
        for pattern in _PHI_VALUE_PATTERNS:
            if pattern.search(value):
                return _REDACTED
        return value
    if isinstance(value, dict):
        return _scrub_dict(value)
    if isinstance(value, (list, tuple)):
        return [_scrub_value(item) for item in value]
    return value


def _scrub_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Return a new dict with PHI keys dropped and PHI values redacted."""
    result: dict[str, Any] = {}
    for key, value in data.items():
        if key.lower() in PHI_BLOCKED_KEYS:
            continue
        result[key] = _scrub_value(value)
    return result


class _FlatJSONHandler(logging.StreamHandler):
    """Emits every log record as a single flat JSON line to stdout.

    CloudWatch captures stdout from Lambda and indexes top-level JSON keys.
    Nested objects are NOT indexed -- all fields must be at the root level.
    """

    def emit(self, record: logging.LogRecord) -> None:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "service": _SERVICE_NAME,
            "stage": _STAGE,
            "function_name": _FUNCTION_NAME,
            "request_id": getattr(record, "request_id", "cold-start"),
            "logger": record.name,
            "message": record.getMessage(),
        }

        extra_fields: dict[str, Any] = getattr(record, "extra_fields", {})
        if extra_fields:
            scrubbed = _scrub_dict(extra_fields)
            entry.update(scrubbed)

        if record.exc_info and record.exc_info[0] is not None:
            formatter = logging.Formatter()
            entry["exception_type"] = record.exc_info[0].__name__
            entry["exception_message"] = str(record.exc_info[1]) if record.exc_info[1] else ""
            entry["stack_trace"] = formatter.formatException(record.exc_info)

        try:
            sys.stdout.write(json.dumps(entry, default=str) + "\n")
            sys.stdout.flush()
        except Exception:  # noqa: BLE001
            pass


# ── Module-level logger registry ─────────────────────────────────────────── #

_registry: dict[str, "Logger"] = {}


class Logger:
    """Structured, PHI-safe logger for Lambda functions.

    All keyword arguments passed to log methods are merged as flat fields into
    the JSON log line.
    """

    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)
        self._logger.setLevel(_LEVEL_INT)
        self._request_id: str = "cold-start"

        if not self._logger.handlers:
            self._logger.addHandler(_FlatJSONHandler())
            self._logger.propagate = False

    def set_request_id(self, request_id: str) -> None:
        """Bind the Lambda invocation request ID for log correlation."""
        self._request_id = request_id

    def _emit(self, level: int, message: str, **fields: Any) -> None:
        extra = {
            "extra_fields": fields,
            "request_id": self._request_id,
        }
        self._logger.log(level, message, extra=extra)

    def debug(self, message: str, **fields: Any) -> None:
        self._emit(logging.DEBUG, message, **fields)

    def info(self, message: str, **fields: Any) -> None:
        self._emit(logging.INFO, message, **fields)

    def warning(self, message: str, **fields: Any) -> None:
        self._emit(logging.WARNING, message, **fields)

    def error(self, message: str, **fields: Any) -> None:
        self._emit(logging.ERROR, message, **fields)

    def critical(self, message: str, **fields: Any) -> None:
        self._emit(logging.CRITICAL, message, **fields)


def get_logger(name: str = __name__) -> Logger:
    """Return a Logger instance, reusing existing instances by name."""
    if name not in _registry:
        _registry[name] = Logger(name)
    return _registry[name]
