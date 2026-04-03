"""PostgreSQL operations for SPEC log data — commands, errors, and processing progress."""

import logging
from datetime import datetime

from db_connection import db_connection

logger = logging.getLogger(__name__)

COMMANDS_TABLE = '"BL15-2_log_commands"'
ERRORS_TABLE = '"BL15-2_log_errors"'
PROGRESS_TABLE = '"BL15-2_log_file_progress"'


def ensure_tables():
    """Create all tables and indexes if they don't exist."""
    with db_connection() as conn:
        cur = conn.cursor()

        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {COMMANDS_TABLE} (
                id SERIAL PRIMARY KEY,
                log_file TEXT NOT NULL,
                command_number INTEGER,
                command_text TEXT NOT NULL,
                timestamp TIMESTAMP,
                inserted_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_log_commands_timestamp
                ON {COMMANDS_TABLE}(timestamp)
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_log_commands_logfile
                ON {COMMANDS_TABLE}(log_file)
        """)

        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {ERRORS_TABLE} (
                id SERIAL PRIMARY KEY,
                log_file TEXT NOT NULL,
                command_text TEXT,
                error_description TEXT NOT NULL,
                timestamp TIMESTAMP,
                inserted_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_log_errors_timestamp
                ON {ERRORS_TABLE}(timestamp)
        """)

        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {PROGRESS_TABLE} (
                log_file TEXT PRIMARY KEY,
                bytes_processed BIGINT NOT NULL DEFAULT 0,
                last_processed_at TIMESTAMP DEFAULT NOW()
            )
        """)

        conn.commit()
        cur.close()


def get_file_progress(log_file: str) -> int:
    """Return bytes_processed for a log file, or 0 if not yet tracked."""
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT bytes_processed FROM {PROGRESS_TABLE} WHERE log_file = %s",
            (log_file,),
        )
        row = cur.fetchone()
        cur.close()
    return row[0] if row else 0


def update_file_progress(log_file: str, bytes_processed: int):
    """Upsert the progress record for a log file."""
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            INSERT INTO {PROGRESS_TABLE} (log_file, bytes_processed, last_processed_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (log_file)
            DO UPDATE SET
                bytes_processed = EXCLUDED.bytes_processed,
                last_processed_at = NOW()
        """, (log_file, bytes_processed))
        conn.commit()
        cur.close()


def reset_file_progress(log_file: str):
    """Delete progress and all commands/errors for a log file (for reprocessing)."""
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM {COMMANDS_TABLE} WHERE log_file = %s", (log_file,))
        cur.execute(f"DELETE FROM {ERRORS_TABLE} WHERE log_file = %s", (log_file,))
        cur.execute(f"DELETE FROM {PROGRESS_TABLE} WHERE log_file = %s", (log_file,))
        conn.commit()
        cur.close()


def insert_commands(commands: list):
    """Batch insert command records.

    Each item should have: log_file, command_number, command_text, timestamp.
    """
    if not commands:
        return
    with db_connection() as conn:
        cur = conn.cursor()
        for cmd in commands:
            cur.execute(f"""
                INSERT INTO {COMMANDS_TABLE}
                    (log_file, command_number, command_text, timestamp)
                VALUES (%s, %s, %s, %s)
            """, (
                cmd["log_file"],
                cmd["command_number"],
                cmd["command_text"],
                cmd.get("timestamp"),
            ))
        conn.commit()
        cur.close()


def insert_errors(errors: list):
    """Batch insert error records.

    Each item should have: log_file, command_text, error_description, timestamp.
    """
    if not errors:
        return
    with db_connection() as conn:
        cur = conn.cursor()
        for err in errors:
            cur.execute(f"""
                INSERT INTO {ERRORS_TABLE}
                    (log_file, command_text, error_description, timestamp)
                VALUES (%s, %s, %s, %s)
            """, (
                err["log_file"],
                err.get("command_text"),
                err["error_description"],
                err.get("timestamp"),
            ))
        conn.commit()
        cur.close()


def get_commands_between_timestamps(start: datetime, end: datetime) -> list:
    """Query log_commands where timestamp BETWEEN start AND end."""
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT log_file, command_number, command_text, timestamp
            FROM {COMMANDS_TABLE}
            WHERE timestamp BETWEEN %s AND %s
            ORDER BY timestamp, command_number
        """, (start, end))
        rows = cur.fetchall()
        cur.close()
    return [
        {"log_file": r[0], "command_number": r[1], "command_text": r[2],
         "timestamp": r[3].isoformat() if r[3] else None}
        for r in rows
    ]


def get_commands_for_logfile(log_file: str, limit: int = 100) -> list:
    """Query log_commands for a specific log file."""
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT log_file, command_number, command_text, timestamp
            FROM {COMMANDS_TABLE}
            WHERE log_file = %s
            ORDER BY command_number
            LIMIT %s
        """, (log_file, limit))
        rows = cur.fetchall()
        cur.close()
    return [
        {"log_file": r[0], "command_number": r[1], "command_text": r[2],
         "timestamp": r[3].isoformat() if r[3] else None}
        for r in rows
    ]


def get_recent_errors(hours: int = 24) -> list:
    """Query log_errors from the last N hours."""
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT log_file, command_text, error_description, timestamp
            FROM {ERRORS_TABLE}
            WHERE timestamp >= NOW() - interval '%s hours'
            ORDER BY timestamp DESC
        """, (hours,))
        rows = cur.fetchall()
        cur.close()
    return [
        {"log_file": r[0], "command_text": r[1], "error_description": r[2],
         "timestamp": r[3].isoformat() if r[3] else None}
        for r in rows
    ]
