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

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:

                # Drop all tables
                _logger.info("Dropping all tables from database...")
                cur.execute("""
                    DO $$ DECLARE
                        r RECORD;
                    BEGIN
                        FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public')
                        LOOP
                            EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                        END LOOP;
                    END $$;
                """)
                conn.commit()
                _logger.info("All tables dropped successfully")

                # Run schema
                _logger.info("Applying schema.sql...")
                schema_sql = _SCHEMA_PATH.read_text()
                if schema_sql.strip():
                    cur.execute(schema_sql)
                    conn.commit()
                    _logger.info("Schema applied successfully")
                else:
                    _logger.info("Schema file is empty, skipping schema creation")

                # Run seed (optional)
                if run_seed:
                    _logger.info("Applying seed.sql...")
                    seed_sql = _SEED_PATH.read_text()
                    if seed_sql.strip():
                        cur.execute(seed_sql)
                        conn.commit()
                        _logger.info("Seed data applied successfully")
                    else:
                        _logger.info("Seed file is empty, skipping seed operation")

        return {"statusCode": 200, "body": "Migration complete"}

    except Exception as exc:
        _logger.error("Migration failed", exc_info=True)
        return {"statusCode": 500, "body": f"Migration failed: {str(exc)}"}