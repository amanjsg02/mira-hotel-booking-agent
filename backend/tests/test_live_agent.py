from uuid import uuid4

import pytest


@pytest.mark.live_ai
def test_live_agent_updates_booking_state(
    client,
):
    session_id = (
        f"live-session-{uuid4().hex}"
    )

    try:
        response = client.post(
            "/api/chat",
            json={
                "request_id": (
                    f"request-{uuid4().hex}"
                ),
                "session_id": session_id,
                "message": (
                    "I need a hotel in Goa from "
                    "5 September 2026 to "
                    "8 September 2026 for "
                    "2 adults under ₹20,000 "
                    "per night."
                ),
            },
        )

        assert response.status_code == 200

        result = response.json()

        assert (
            result["state"]["destination"]
            == "Goa"
        )

        assert (
            result["state"]["guests"]["adults"]
            == 2
        )

        assert (
            result["state"]["budget_per_night"]
            == 20000
        )

        assert result.get(
            "agent_mode"
        ) in {
            "phase2",
            "gemini",
        }

        model_name = result.get(
            "model_name"
        )

        assert model_name is not None
        assert "gemini" in (
            model_name.casefold()
        )

        tool_names = [
            trace.get("tool")
            or trace.get("tool_name")
            for trace in result.get(
                "tool_traces",
                []
            )
        ]

        assert (
            "update_booking_state"
            in tool_names
        )

    finally:
        client.delete(
            f"/api/sessions/{session_id}"
        )