"""Central observability module — Logger, Tracer, Metrics.

All Lambda functions import from here. Never instantiate Logger/Tracer/Metrics
in any other module. One instance per function container, reused across all
warm invocations.

Usage in any module:
    from src.shared.observability import logger, tracer, metrics
"""

import re
from typing import Any

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging.formatter import LambdaPowertoolsFormatter

# ── PHI protection constants ─────────────────────────────────────────────── #
# Kept identical to the original logger.py to preserve existing scrub behaviour.

_PHI_BLOCKED_KEYS: frozenset[str] = frozenset({
    "email", "phone", "dob", "date_of_birth", "birth_date",
    "first_name", "last_name", "full_name", "name",
    "address", "street", "city", "zip", "postal_code",
    "ssn", "social_security",
    "note_text", "notes",
    "medication_name", "medication", "dosage", "dose",
    "diagnosis", "icd10_code", "icd_code", "condition_name", "condition",
    "password", "secret", "token", "api_key", "key",
    "credential", "auth", "authorization",
    "topic",   # derived from condition_name + icd10_code in education module
})

_PHI_VALUE_PATTERNS: list[re.Pattern] = [
    re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE),
    re.compile(r"^\+?[1-9]\d{7,14}$"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
]

_REDACTED = "[REDACTED]"


def _scrub_value(value: Any) -> Any:
    """Redact PHI string values; recurse into dicts and lists."""
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
    """Drop blocked PHI keys and redact PHI values from a log dict."""
    return {
        key: _scrub_value(value)
        for key, value in data.items()
        if key.lower() not in _PHI_BLOCKED_KEYS
    }


# ── PHI-safe Powertools formatter ─────────────────────────────────────────── #

class PHISafeFormatter(LambdaPowertoolsFormatter):
    """Powertools formatter with dual-layer PHI scrubbing.

    Extends the standard Powertools formatter — all structured fields
    pass through the PHI scrubber before serialisation to JSON.
    """

    def serialize(self, log: dict) -> str:  # type: ignore[override]
        """Scrub PHI from every log dict before serialising to JSON."""
        return super().serialize(_scrub_dict(log))


# ── Singleton instances — one per container, reused across warm invocations ── #
# POWERTOOLS_SERVICE_NAME, POWERTOOLS_METRICS_NAMESPACE, LOG_LEVEL are set via
# environment variables in serverless.yml — never hardcoded here.

logger = Logger(
    logger_formatter=PHISafeFormatter(),
    log_uncaught_exceptions=True,   # Catches unhandled exceptions automatically
    serialize_stacktrace=True,      # Stack traces as structured JSON, not plain strings
)

tracer = Tracer()

metrics = Metrics()
