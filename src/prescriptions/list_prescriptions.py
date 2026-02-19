"""GET /patients/{patient_id}/prescriptions — lists prescriptions with status filter."""

import time
from typing import Any

from src.shared import db, response
from src.shared.exceptions import HealthcarePlatformError, RecordNotFoundError
from src.shared.logger import get_logger
from src.shared.request_validator import validate_query_param_enum, validate_uuid_path_param
from src.prescriptions.schemas import PRESCRIPTION_STATUS_VALUES


_logger = get_logger(__name__)

_CHECK_PATIENT_EXISTS = "SELECT id FROM patients WHERE id = %s AND status = 'active'"

_BASE_QUERY = """
    SELECT
        rx.id               AS prescription_id,
        rx.medication_name,
        rx.dosage,
        rx.frequency,
        rx.start_date,
        rx.end_date,
        rx.status,
        p.id                AS provider_id,
        p.first_name        AS provider_first_name,
        p.last_name         AS provider_last_name
    FROM prescriptions rx
    JOIN providers p ON p.id = rx.provider_id
    WHERE rx.patient_id = %s
"""

_ACTIVE_FILTER = " AND rx.status = 'active'"
_PAST_FILTER = " AND rx.status IN ('completed', 'cancelled')"
_ORDER_BY = " ORDER BY rx.start_date DESC"


def _build_query(status_filter: str) -> str:
    """Append the appropriate WHERE clause for the requested filter."""
    if status_filter == "active":
        return _BASE_QUERY + _ACTIVE_FILTER + _ORDER_BY
    if status_filter == "past":
        return _BASE_QUERY + _PAST_FILTER + _ORDER_BY
    return _BASE_QUERY + _ORDER_BY


def _format_prescription(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "prescription_id": str(row["prescription_id"]),
        "medication_name": row["medication_name"],
        "dosage": row["dosage"],
        "frequency": row["frequency"],
        "start_date": row["start_date"].isoformat() if row["start_date"] else None,
        "end_date": row["end_date"].isoformat() if row["end_date"] else None,
        "status": row["status"],
        "prescribed_by": {
            "provider_id": str(row["provider_id"]),
            "full_name": f"Dr. {row['provider_first_name']} {row['provider_last_name']}",
        },
    }


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for GET /patients/{patient_id}/prescriptions."""
    _logger.set_request_id(context.aws_request_id)
    start = time.perf_counter()

    path_params = event.get("pathParameters") or {}
    query_params = event.get("queryStringParameters") or {}
    _logger.info("Prescription list request received")

    try:
        patient_id = validate_uuid_path_param(path_params.get("patient_id"), "patient_id")
        status_filter = validate_query_param_enum(
            query_params.get("filter"),
            "filter",
            PRESCRIPTION_STATUS_VALUES,
            default="active",
        )

        patient_rows = db.execute_query(_CHECK_PATIENT_EXISTS, (patient_id,))
        if not patient_rows:
            raise RecordNotFoundError("Patient not found")

        query = _build_query(status_filter)
        rows = db.execute_query(query, (patient_id,))
        prescriptions = [_format_prescription(row) for row in rows]

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.info(
            "Prescriptions listed",
            patient_id=patient_id,
            filter=status_filter,
            count=len(prescriptions),
            duration_ms=elapsed_ms,
        )

        return response.success(
            data={"prescriptions": prescriptions, "total": len(prescriptions)},
            meta={"filter": status_filter},
        )

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.warning(
            "Prescription list request failed",
            error_code=exc.error_code,
            duration_ms=elapsed_ms,
        )
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.error(
            "Unexpected error listing prescriptions",
            duration_ms=elapsed_ms,
        )
        return response.error(
            message="An unexpected error occurred",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )
