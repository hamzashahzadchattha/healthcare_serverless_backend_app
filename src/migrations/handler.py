"""One-off database migration runner. Invoke once manually, never via API Gateway."""

import os
from pathlib import Path
from typing import Any

from src.shared.db import get_connection
from src.shared.observability import logger

_SCHEMA_PATH = Path(__file__).parent.parent.parent / "db" / "schema.sql"
_SEED_PATH = Path(__file__).parent.parent.parent / "db" / "seed.sql"


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Execute schema.sql then seed.sql against the RDS instance."""
    run_seed = event.get("seed", True)

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:

                # Drop all tables
                logger.info("Dropping all tables from database...")
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
                logger.info("All tables dropped successfully")

                # Run schema
                logger.info("Applying schema.sql...")
                schema_sql = _SCHEMA_PATH.read_text()
                if schema_sql.strip():
                    cur.execute(schema_sql)
                    conn.commit()
                    logger.info("Schema applied successfully")
                else:
                    logger.info("Schema file is empty, skipping schema creation")

                # Run seed (optional)
                if run_seed:
                    logger.info("Applying seed.sql...")
                    seed_sql = _SEED_PATH.read_text()
                    if seed_sql.strip():
                        cur.execute(seed_sql)
                        conn.commit()
                        logger.info("Seed data applied successfully")
                    else:
                        logger.info("Seed file is empty, skipping seed operation")

        return {"statusCode": 200, "body": "Migration complete"}

    except Exception as exc:
        logger.exception("Migration failed")
        return {"statusCode": 500, "body": f"Migration failed: {str(exc)}"}