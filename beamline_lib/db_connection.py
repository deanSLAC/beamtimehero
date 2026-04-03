"""Shared database connection management with contextvars-based reuse.

Provides a reentrant context manager that ensures connections are always
closed (even on exceptions) and allows nested function calls to reuse
the same connection automatically.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar

import psycopg2

from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

logger = logging.getLogger(__name__)

_current_conn: ContextVar[psycopg2.extensions.connection | None] = ContextVar(
    "_current_conn", default=None
)


def _create_connection() -> psycopg2.extensions.connection:
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD,
    )


@contextmanager
def db_connection():
    """Context manager providing a DB connection with guaranteed cleanup.

    Reentrant: if a connection is already active in the current context
    (from an outer call), it is reused and NOT closed by the inner block.
    Only the outermost context manager closes the connection.
    """
    existing = _current_conn.get(None)
    if existing is not None and not existing.closed:
        yield existing
        return

    conn = _create_connection()
    token = _current_conn.set(conn)
    try:
        yield conn
    finally:
        _current_conn.reset(token)
        try:
            conn.close()
        except Exception:
            logger.warning("Error closing DB connection", exc_info=True)
