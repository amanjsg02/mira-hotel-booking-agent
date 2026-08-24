from app.models import ConversationState
from app.services.session_store import (
    session_store,
)


def test_session_state_is_saved(
    unique_session_id: str,
):
    state = ConversationState()

    state.destination = "Goa"
    state.guests.adults = 2
    state.budget_per_night = 20000

    session_store.save(
        unique_session_id,
        state,
    )

    restored = session_store.get(
        unique_session_id
    )

    assert restored.destination == "Goa"
    assert restored.guests.adults == 2
    assert restored.budget_per_night == 20000

    session_store.clear(unique_session_id)


def test_sessions_are_independent():
    session_a = "test-independent-goa"
    session_b = "test-independent-jaipur"

    try:
        state_a = ConversationState()
        state_a.destination = "Goa"
        state_a.guests.adults = 2

        state_b = ConversationState()
        state_b.destination = "Jaipur"
        state_b.guests.adults = 4

        session_store.save(
            session_a,
            state_a,
        )
        session_store.save(
            session_b,
            state_b,
        )

        restored_a = session_store.get(
            session_a
        )
        restored_b = session_store.get(
            session_b
        )

        assert restored_a.destination == "Goa"
        assert restored_a.guests.adults == 2

        assert restored_b.destination == "Jaipur"
        assert restored_b.guests.adults == 4
    finally:
        session_store.clear(session_a)
        session_store.clear(session_b)


def test_messages_are_persisted(
    stored_session_id: str,
):
    session_store.save_message(
        session_id=stored_session_id,
        role="guest",
        content="I need a hotel in Goa.",
    )

    session_store.save_message(
        session_id=stored_session_id,
        role="agent",
        content="How many guests are travelling?",
    )

    messages = session_store.get_messages(
        stored_session_id
    )

    assert len(messages) == 2
    assert messages[0].role == "guest"
    assert messages[1].role == "agent"


def test_clear_deletes_session(
    unique_session_id: str,
):
    session_store.get(unique_session_id)

    assert session_store.exists(
        unique_session_id
    )

    deleted_count = session_store.clear(
        unique_session_id
    )

    assert deleted_count == 1
    assert not session_store.exists(
        unique_session_id
    )


def test_clear_deletes_messages(
    unique_session_id: str,
):
    session_store.save_message(
        session_id=unique_session_id,
        role="guest",
        content="Temporary message",
    )

    session_store.clear(unique_session_id)

    messages = session_store.get_messages(
        unique_session_id
    )

    assert messages == []