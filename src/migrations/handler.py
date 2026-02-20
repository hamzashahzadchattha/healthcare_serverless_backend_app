"""One-off database migration runner. Invoke once manually, never via API Gateway."""

import os
from pathlib import Path
from typing import Any

from src.shared.db import get_connection
from src.shared.logger import get_logger

_logger = get_logger(__name__)

_SCHEMA_PATH = Path(__file__).parent.parent.parent / "db" / "schema.sql"
_SEED_PATH = Path(__file__).parent.parent.parent / "db" / "seed.sql"


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Execute schema.sql then seed.sql against the RDS instance."""
    _logger.set_request_id(context.aws_request_id)
    run_seed = event.get("seed", False)

    _logger.info("Starting schema migration")

    try:
        schema_sql = _SCHEMA_PATH.read_text()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(schema_sql)
            conn.commit()

        _logger.info("Schema applied successfully")

        if run_seed:
            seed_sql = _SEED_PATH.read_text()
            if seed_sql.strip():
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(seed_sql)
                    conn.commit()
                _logger.info("Seed data applied successfully")
            else:
                _logger.info("Seed file is empty, skipping seed operation")

        return {"statusCode": 200, "body": "Migration complete"}
    except Exception as exc:
        _logger.error("Migration failed", exc_info=True)
        return {"statusCode": 500, "body": f"Migration failed: {str(exc)}"}
