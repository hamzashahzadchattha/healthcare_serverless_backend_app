"""RDS PostgreSQL connection pool manager for Lambda warm-start reuse."""

import os
import time
from contextlib import contextmanager
from typing import Any, Generator

import psycopg2
import psycopg2.extras
import psycopg2.pool

from src.shared.exceptions import DatabaseConnectionError, DatabaseQueryError
from src.shared.logger import get_logger
from src.shared.secrets import get_secret, invalidate

_logger = get_logger(__name__)

_DB_SECRET_NAME = os.environ.get("DB_SECRET_NAME", "")

_pool: psycopg2.pool.ThreadedConnectionPool | None = None

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
        f"sslmode=prefer "
        f"connect_timeout=5"
    )


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """Return the module-level connection pool, creating it on first call."""
    global _pool  # noqa: PLW0603
    if _pool is None or _pool.closed:
        creds = get_secret(_DB_SECRET_NAME)

        db_host = os.environ.get("DB_HOST")
        db_name = os.environ.get("DB_NAME")
        _logger.info("Connecting to DB", host=db_host, dbname=db_name)

        dsn = _build_dsn(creds)
        try:
            _pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=5,
                dsn=dsn,
                cursor_factory=psycopg2.extras.RealDictCursor,
            )
            _logger.info("Database connection pool created", minconn=1, maxconn=5)
        except psycopg2.OperationalError as exc:
            raise DatabaseConnectionError(
                "Failed to create database connection pool",
            ) from exc
    return _pool


def _reset_pool() -> None:
    """Close all connections, destroy the pool, and invalidate cached credentials."""
    global _pool  # noqa: PLW0603
    if _pool is not None:
        try:
            _pool.closeall()
        except Exception:
            pass
    _pool = None
    invalidate(_DB_SECRET_NAME)


@contextmanager
def get_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """Borrow a connection from the pool and return it on exit.

    Retries once on OperationalError by resetting the pool.
    """
    conn = None
    pool = None
    for attempt in range(_MAX_RETRIES):
        try:
            pool = _get_pool()
            conn = pool.getconn()
            break
        except psycopg2.OperationalError:
            if attempt == _MAX_RETRIES - 1:
                raise DatabaseConnectionError(
                    "Failed to obtain database connection after retry",
                )
            _logger.warning("Stale DB connection detected, resetting pool")
            _reset_pool()

    try:
        yield conn  # type: ignore[misc]
    finally:
        if conn is not None and pool is not None:
            pool.putconn(conn)


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
                _logger.debug(
                    "Query executed",
                    query_template=query.strip()[:200],
                    duration_ms=round(elapsed_ms, 2),
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
                        _logger.debug(
                            "Transaction step executed", query_template=query.strip()[:200]
                        )
                        if not rows and cur.description is not None:
                            rows = [dict(row) for row in cur.fetchall()]
                conn.commit()
                elapsed_ms = (time.perf_counter() - start) * 1000
                _logger.info(
                    "Transaction committed",
                    steps=len(operations),
                    duration_ms=round(elapsed_ms, 2),
                )
            except psycopg2.DatabaseError as exc:
                conn.rollback()
                _logger.error("Transaction rolled back", error=str(exc))
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
