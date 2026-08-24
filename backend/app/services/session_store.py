import json
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from app.database.sqlite import (
    get_connection,
    initialize_database,
)
from app.models import (
    ChatResponse,
    ConversationMessage,
    ConversationState,
    ToolTrace,
)


class SQLiteSessionStore:
    """
    Persistent SQLite conversation storage.

    This keeps the same get/save/clear interface used by the
    existing orchestrators.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        initialize_database()

    @staticmethod
    def _now() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()

    @staticmethod
    def _validate_session_id(
        session_id: str,
    ) -> str:
        if not isinstance(session_id, str):
            raise TypeError(
                "session_id must be a string."
            )

        normalized = session_id.strip()

        if not normalized:
            raise ValueError(
                "session_id cannot be empty."
            )

        if len(normalized) > 128:
            raise ValueError(
                "session_id is too long."
            )

        return normalized

    def get(
        self,
        session_id: str,
    ) -> ConversationState:
        session_id = self._validate_session_id(
            session_id
        )

        with self._lock:
            with get_connection() as connection:
                row = connection.execute(
                    """
                    SELECT state_json
                    FROM conversation_sessions
                    WHERE session_id = ?
                    """,
                    (session_id,),
                ).fetchone()

                if row is not None:
                    return (
                        ConversationState
                        .model_validate_json(
                            row["state_json"]
                        )
                    )

                state = ConversationState()
                now = self._now()

                connection.execute(
                    """
                    INSERT INTO conversation_sessions (
                        session_id,
                        state_json,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        state.model_dump_json(),
                        now,
                        now,
                    ),
                )

                return state

    def save(
        self,
        session_id: str,
        state: ConversationState,
    ) -> ConversationState:
        session_id = self._validate_session_id(
            session_id
        )

        if not isinstance(
            state,
            ConversationState,
        ):
            raise TypeError(
                "state must be ConversationState."
            )

        stored_state = state.model_copy(
            deep=True
        )

        now = self._now()

        with self._lock:
            with get_connection() as connection:
                connection.execute(
                    """
                    INSERT INTO conversation_sessions (
                        session_id,
                        state_json,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(session_id)
                    DO UPDATE SET
                        state_json = excluded.state_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        session_id,
                        stored_state.model_dump_json(),
                        now,
                        now,
                    ),
                )

        return stored_state.model_copy(
            deep=True
        )

    def exists(
        self,
        session_id: str,
    ) -> bool:
        session_id = self._validate_session_id(
            session_id
        )

        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM conversation_sessions
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()

        return row is not None

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> ConversationMessage:
        """
        Save one guest or agent message.
        """
        self.get(session_id)

        message = ConversationMessage(
            message_id=(
                f"msg-{uuid4().hex}"
            ),
            session_id=session_id,
            role=role,
            content=content,
        )

        with self._lock:
            with get_connection() as connection:
                connection.execute(
                    """
                    INSERT INTO conversation_messages (
                        message_id,
                        session_id,
                        role,
                        content,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        message.message_id,
                        message.session_id,
                        message.role,
                        message.content,
                        message.created_at.isoformat(),
                    ),
                )

        return message

    def get_messages(
        self,
        session_id: str,
        limit: int = 100,
    ) -> list[ConversationMessage]:
        """
        Return messages in chronological order.
        """
        session_id = self._validate_session_id(
            session_id
        )

        limit = max(1, min(limit, 500))

        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    message_id,
                    session_id,
                    role,
                    content,
                    created_at
                FROM conversation_messages
                WHERE session_id = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (
                    session_id,
                    limit,
                ),
            ).fetchall()

        return [
            ConversationMessage(
                message_id=row["message_id"],
                session_id=row["session_id"],
                role=row["role"],
                content=row["content"],
                created_at=datetime.fromisoformat(
                    row["created_at"]
                ),
            )
            for row in rows
        ]

    def save_tool_traces(
        self,
        session_id: str,
        traces: list[ToolTrace],
    ) -> None:
        """
        Persist observable tool executions.
        """
        if not traces:
            return

        self.get(session_id)

        now = self._now()

        rows = []

        for trace in traces:
            rows.append((
                f"exec-{uuid4().hex}",
                session_id,
                trace.tool,
                json.dumps(
                    trace.arguments,
                    default=str,
                ),
                json.dumps(
                    trace.result,
                    default=str,
                ),
                trace.status,
                now,
            ))

        with self._lock:
            with get_connection() as connection:
                connection.executemany(
                    """
                    INSERT INTO tool_executions (
                        execution_id,
                        session_id,
                        tool_name,
                        arguments_json,
                        result_json,
                        status,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )

    def get_tool_traces(
        self,
        session_id: str,
        limit: int = 100,
    ) -> list[dict]:
        session_id = self._validate_session_id(
            session_id
        )

        limit = max(1, min(limit, 500))

        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    execution_id,
                    tool_name,
                    arguments_json,
                    result_json,
                    status,
                    created_at
                FROM tool_executions
                WHERE session_id = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (
                    session_id,
                    limit,
                ),
            ).fetchall()

        return [
            {
                "execution_id": row[
                    "execution_id"
                ],
                "tool_name": row["tool_name"],
                "arguments": json.loads(
                    row["arguments_json"]
                ),
                "result": json.loads(
                    row["result_json"]
                ),
                "status": row["status"],
                "created_at": row[
                    "created_at"
                ],
            }
            for row in rows
        ]

    def get_processed_response(
        self,
        request_id: str,
    ) -> ChatResponse | None:
        """
        Return an existing response for a duplicate request.
        """
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT response_json
                FROM processed_requests
                WHERE request_id = ?
                """,
                (request_id,),
            ).fetchone()

        if row is None:
            return None

        return ChatResponse.model_validate_json(
            row["response_json"]
        )

    def save_processed_response(
        self,
        request_id: str,
        session_id: str,
        response: ChatResponse,
    ) -> None:
        """
        Store the result of a processed request.
        """
        self.get(session_id)

        with self._lock:
            with get_connection() as connection:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO
                    processed_requests (
                        request_id,
                        session_id,
                        response_json,
                        created_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        request_id,
                        session_id,
                        response.model_dump_json(),
                        self._now(),
                    ),
                )

    def clear(
        self,
        session_id: str | None = None,
    ) -> int:
        """
        Permanently delete one session or every session.

        Child records are removed explicitly so deletion
        works even if an older SQLite database was created
        without ON DELETE CASCADE constraints.

        Returns the number of deleted conversation sessions.
        """
        with self._lock:
            with get_connection() as connection:
                if session_id is None:
                    row = connection.execute(
                        """
                        SELECT COUNT(*) AS total
                        FROM conversation_sessions
                        """
                    ).fetchone()

                    deleted_count = (
                        row["total"]
                        if row is not None
                        else 0
                    )

                    connection.execute(
                        "DELETE FROM processed_requests"
                    )
                    connection.execute(
                        "DELETE FROM tool_executions"
                    )
                    connection.execute(
                        "DELETE FROM booking_holds"
                    )
                    connection.execute(
                        "DELETE FROM conversation_messages"
                    )

                    connection.execute(
                        """
                        DELETE FROM conversation_sessions
                        """
                    )

                    connection.commit()

                    return deleted_count

                validated_session_id = (
                    self._validate_session_id(
                        session_id
                    )
                )

                connection.execute(
                    """
                    DELETE FROM processed_requests
                    WHERE session_id = ?
                    """,
                    (validated_session_id,),
                )

                connection.execute(
                    """
                    DELETE FROM tool_executions
                    WHERE session_id = ?
                    """,
                    (validated_session_id,),
                )

                connection.execute(
                    """
                    DELETE FROM booking_holds
                    WHERE session_id = ?
                    """,
                    (validated_session_id,),
                )

                connection.execute(
                    """
                    DELETE FROM conversation_messages
                    WHERE session_id = ?
                    """,
                    (validated_session_id,),
                )

                result = connection.execute(
                    """
                    DELETE FROM conversation_sessions
                    WHERE session_id = ?
                    """,
                    (validated_session_id,),
                )

                connection.commit()

                return max(result.rowcount, 0)

    def count(self) -> int:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM conversation_sessions
                """
            ).fetchone()

            return (
                row["total"]
                if row is not None
                else 0
            )


session_store = SQLiteSessionStore()