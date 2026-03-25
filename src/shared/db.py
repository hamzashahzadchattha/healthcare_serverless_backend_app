"""RDS PostgreSQL connection manager for Lambda warm-start reuse.

Uses a single module-level psycopg2 connection per Lambda container.
RDS Proxy manages pooling across invocations/containers; this module
only ensures we reuse the same connection during warm invocations.
"""

import os
import threading
import time
from contextlib import contextmanager
from typing import Any, Generator

import psycopg2
import psycopg2.extras

from src.shared.exceptions import DatabaseConnectionError, DatabaseQueryError
from src.shared.observability import logger
from src.shared.parameters import get_db_credentials

_conn: psycopg2.extensions.connection | None = None
_conn_lock = threading.Lock()

_MAX_RETRIES = 2


def _build_dsn(creds: dict[str, Any]) -> str:
    """Construct a PostgreSQL DSN from Secrets Manager credentials and Env variables."""
    # CloudFormation MasterUserSecret only provides username and password by default.
    return (
        f"host={os.environ.get('DB_HOST')} "
        f"port={os.environ.get('DB_PORT', '5432')} "
        f"dbname={os.environ.get('DB_NAME')} "
        f"user={creds.get('username', '')} "
        f"password={creds.get('password', '')} "
        # RDS Proxy can enforce TLS; using `require` ensures encryption is used.
        f"sslmode=require "
        f"connect_timeout=5"
    )


def _reset_connection() -> None:
    """Close the cached connection and force-refresh cached credentials."""
    global _conn  # noqa: PLW0603
    if _conn is not None:
        try:
            _conn.close()
        except Exception:
            pass
    _conn = None

    try:
        # Handles password rotation scenarios where the proxy continues using
        # the old credentials until refreshed.
        get_db_credentials(force_refresh=True)
    except Exception:
        pass


def _get_connection() -> psycopg2.extensions.connection:
    """Return the module-level connection, creating it on first use."""
    global _conn  # noqa: PLW0603
    if _conn is None or getattr(_conn, "closed", 1) != 0:
        creds = get_db_credentials()

        db_host = os.environ.get("DB_HOST")
        db_name = os.environ.get("DB_NAME")
        logger.info("Connecting to DB", extra={"host": db_host, "dbname": db_name})

        dsn = _build_dsn(creds)
        try:
            _conn = psycopg2.connect(
                dsn,
                cursor_factory=psycopg2.extras.RealDictCursor,
            )
        except psycopg2.OperationalError as exc:
            raise DatabaseConnectionError("Failed to establish database connection") from exc

    return _conn


@contextmanager
def get_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """Yield a cached connection without closing it.

    Retries once on OperationalError by resetting the connection.
    """
    conn: psycopg2.extensions.connection | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            with _conn_lock:
                conn = _get_connection()
            break
        except psycopg2.OperationalError:
            if attempt == _MAX_RETRIES - 1:
                raise DatabaseConnectionError(
                    "Failed to obtain database connection after retry",
                )
            logger.warning("Stale DB connection detected, resetting connection")
            with _conn_lock:
                _reset_connection()

    try:
        yield conn  # type: ignore[misc]
    finally:
        # Connection lifecycle is managed by Lambda container reuse.
        # Intentionally do not close the connection here.
        pass


def execute_query(
    query: str,
    params: tuple[Any, ...] | None = None,
    *,
    fetch: bool = True,
    commit: bool = True,
) -> list[dict[str, Any]]:
    """Execute a SQL query and optionally return rows.

    Args:
        query: Parameterised SQL string. Use %s placeholders.
        params: Query parameters. Never interpolated directly into the string.
        fetch: When True, fetchall and return rows.
        commit: When True, commit after execution. Required for INSERT/UPDATE/DELETE.

    Returns:
        List of row dicts (empty list for non-fetch calls).

    Raises:
        DatabaseQueryError: On any psycopg2 database error.
    """
    start = time.perf_counter()
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.debug(
                    "Query executed",
                    extra={
                        "query_template": query.strip()[:200],
                        "duration_ms": round(elapsed_ms, 2),
                    },
                )
                rows: list[dict[str, Any]] = []
                if fetch:
                    rows = [dict(row) for row in cur.fetchall()]
                if commit:
                    conn.commit()
                return rows
    except psycopg2.IntegrityError as exc:
        raise DatabaseQueryError(
            "Database integrity constraint violated",
            details={"pg_error": str(exc.pgerror or "")},
        ) from exc
    except psycopg2.DatabaseError as exc:
        raise DatabaseQueryError("Database query failed") from exc


def execute_transaction(
    operations: list[tuple[str, tuple[Any, ...] | None]],
) -> list[dict[str, Any]]:
    """Execute multiple SQL statements in a single atomic transaction.

    All operations succeed together or all are rolled back.
    Rows from the first operation that contains a RETURNING clause are returned.
    This matches the common pattern of INSERT...RETURNING followed by UPDATE.

    Args:
        operations: List of (query_template, params) tuples to execute in order.

    Returns:
        Rows from the first RETURNING result encountered, otherwise empty list.

    Raises:
        DatabaseQueryError: On any failure -- all changes are rolled back.
    """
    start = time.perf_counter()
    rows: list[dict[str, Any]] = []
    try:
        with get_connection() as conn:
            conn.autocommit = False
            try:
                with conn.cursor() as cur:
                    for query, params in operations:
                        cur.execute(query, params)
                        logger.debug(
                            "Transaction step executed", extra={"query_template": query.strip()[:200]}
                        )
                        if not rows and cur.description is not None:
                            rows = [dict(row) for row in cur.fetchall()]
                conn.commit()
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.info(
                    "Transaction committed",
                    extra={
                        "steps": len(operations),
                        "duration_ms": round(elapsed_ms, 2),
                    },
                )
            except psycopg2.DatabaseError as exc:
                conn.rollback()
                logger.exception("Transaction rolled back")
                raise DatabaseQueryError(
                    "Transaction failed and was rolled back",
                ) from exc
            finally:
                conn.autocommit = True
    except DatabaseQueryError:
        raise
    except psycopg2.DatabaseError as exc:
        raise DatabaseQueryError("Database transaction failed") from exc
    return rows
