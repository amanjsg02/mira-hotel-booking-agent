import json
from datetime import datetime, timezone
from threading import RLock

from app.database.sqlite import (
    get_connection,
    initialize_database,
)
from app.models import BookingHold


class SQLiteHoldRepository:
    """
    Persistent booking-hold repository.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        initialize_database()

    def save(
        self,
        hold: BookingHold,
    ) -> BookingHold:
        with self._lock:
            with get_connection() as connection:
                connection.execute(
                    """
                    INSERT INTO booking_holds (
                        hold_id,
                        session_id,
                        property_id,
                        property_name,
                        room_id,
                        room_name,
                        check_in,
                        check_out,
                        guest_count,
                        selected_add_ons_json,
                        currency,
                        total,
                        status,
                        created_at,
                        expires_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?
                    )
                    ON CONFLICT(hold_id)
                    DO UPDATE SET
                        status = excluded.status,
                        selected_add_ons_json =
                            excluded.selected_add_ons_json,
                        total = excluded.total,
                        expires_at = excluded.expires_at
                    """,
                    (
                        hold.hold_id,
                        hold.session_id,
                        hold.property_id,
                        hold.property_name,
                        hold.room_id,
                        hold.room_name,
                        hold.check_in.isoformat(),
                        hold.check_out.isoformat(),
                        hold.guest_count,
                        json.dumps(
                            hold.selected_add_ons
                        ),
                        hold.currency,
                        hold.total,
                        hold.status,
                        hold.created_at.isoformat(),
                        hold.expires_at.isoformat(),
                    ),
                )

        return hold.model_copy(deep=True)

    def get(
        self,
        hold_id: str,
    ) -> BookingHold | None:
        with self._lock:
            with get_connection() as connection:
                row = connection.execute(
                    """
                    SELECT *
                    FROM booking_holds
                    WHERE hold_id = ?
                    """,
                    (hold_id,),
                ).fetchone()

                if row is None:
                    return None

                hold = self._from_row(row)

                if (
                    hold.status == "held"
                    and datetime.now(timezone.utc)
                    >= hold.expires_at
                ):
                    hold.status = "expired"

                    connection.execute(
                        """
                        UPDATE booking_holds
                        SET status = 'expired'
                        WHERE hold_id = ?
                        """,
                        (hold_id,),
                    )

                return hold

    def list_for_session(
        self,
        session_id: str,
    ) -> list[BookingHold]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM booking_holds
                WHERE session_id = ?
                ORDER BY created_at DESC
                """,
                (session_id,),
            ).fetchall()

        return [
            self.get(row["hold_id"])
            for row in rows
            if self.get(row["hold_id"])
            is not None
        ]

    def cancel(
        self,
        hold_id: str,
    ) -> BookingHold | None:
        hold = self.get(hold_id)

        if hold is None:
            return None

        if hold.status == "expired":
            return hold

        with self._lock:
            with get_connection() as connection:
                connection.execute(
                    """
                    UPDATE booking_holds
                    SET status = 'cancelled'
                    WHERE hold_id = ?
                    """,
                    (hold_id,),
                )

        hold.status = "cancelled"

        return hold

    @staticmethod
    def _from_row(
        row,
    ) -> BookingHold:
        return BookingHold(
            hold_id=row["hold_id"],
            session_id=row["session_id"],
            property_id=row["property_id"],
            property_name=row["property_name"],
            room_id=row["room_id"],
            room_name=row["room_name"],
            check_in=row["check_in"],
            check_out=row["check_out"],
            guest_count=row["guest_count"],
            selected_add_ons=json.loads(
                row["selected_add_ons_json"]
            ),
            currency=row["currency"],
            total=row["total"],
            status=row["status"],
            created_at=datetime.fromisoformat(
                row["created_at"]
            ),
            expires_at=datetime.fromisoformat(
                row["expires_at"]
            ),
        )


hold_repository = SQLiteHoldRepository()