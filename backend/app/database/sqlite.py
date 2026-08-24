import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(override=True)


BACKEND_DIRECTORY = (
    Path(__file__).resolve().parents[2]
)

configured_path = os.getenv(
    "DATABASE_PATH",
    "data/hotel_agent.db",
)

DATABASE_PATH = Path(configured_path)

if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = (
        BACKEND_DIRECTORY / DATABASE_PATH
    )

DATABASE_PATH.parent.mkdir(
    parents=True,
    exist_ok=True,
)


def get_connection() -> sqlite3.Connection:
    """
    Create a SQLite connection.

    A new connection is created for each repository operation,
    making it safer with FastAPI threads.
    """
    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    connection.execute(
        "PRAGMA journal_mode = WAL"
    )

    return connection


def initialize_database() -> None:
    """
    Create all Phase 4 tables if they do not exist.
    """
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversation_sessions (
                session_id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conversation_messages (
                message_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL
                    CHECK(role IN ('guest', 'agent')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id)
                    REFERENCES conversation_sessions(session_id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS
                idx_messages_session_created
            ON conversation_messages(
                session_id,
                created_at
            );

            CREATE TABLE IF NOT EXISTS tool_executions (
                execution_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                arguments_json TEXT NOT NULL,
                result_json TEXT,
                status TEXT NOT NULL
                    CHECK(status IN ('success', 'error')),
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id)
                    REFERENCES conversation_sessions(session_id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS
                idx_tools_session_created
            ON tool_executions(
                session_id,
                created_at
            );

            CREATE TABLE IF NOT EXISTS booking_holds (
                hold_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                property_id TEXT NOT NULL,
                property_name TEXT NOT NULL,
                room_id TEXT NOT NULL,
                room_name TEXT NOT NULL,
                check_in TEXT NOT NULL,
                check_out TEXT NOT NULL,
                guest_count INTEGER NOT NULL,
                selected_add_ons_json TEXT NOT NULL,
                currency TEXT NOT NULL,
                total INTEGER NOT NULL,
                status TEXT NOT NULL
                    CHECK(
                        status IN (
                            'held',
                            'expired',
                            'cancelled'
                        )
                    ),
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(session_id)
                    REFERENCES conversation_sessions(session_id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS
                idx_holds_session
            ON booking_holds(session_id);

            CREATE TABLE IF NOT EXISTS processed_requests (
                request_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id)
                    REFERENCES conversation_sessions(session_id)
                    ON DELETE CASCADE
            );
            """
        )