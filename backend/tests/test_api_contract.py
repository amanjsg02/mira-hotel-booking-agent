from uuid import uuid4

import pytest


@pytest.mark.integration
def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200


@pytest.mark.integration
def test_agent_status_endpoint(client):
    response = client.get(
        "/api/agent/status"
    )

    assert response.status_code == 200

    body = response.json()

    assert "phase" in body
    assert "provider" in body
    assert "ai_agent_enabled" in body
    assert "api_key_configured" in body


@pytest.mark.integration
def test_chat_rejects_empty_message(client):
    response = client.post(
        "/api/chat",
        json={
            "request_id": (
                f"request-{uuid4().hex}"
            ),
            "session_id": (
                f"session-{uuid4().hex}"
            ),
            "message": "",
        },
    )

    assert response.status_code == 422


@pytest.mark.integration
def test_chat_rejects_missing_request_id(
    client,
):
    response = client.post(
        "/api/chat",
        json={
            "session_id": (
                f"session-{uuid4().hex}"
            ),
            "message": "Find a hotel in Goa.",
        },
    )

    assert response.status_code == 422


@pytest.mark.integration
def test_chat_rejects_missing_session_id(
    client,
):
    response = client.post(
        "/api/chat",
        json={
            "request_id": (
                f"request-{uuid4().hex}"
            ),
            "message": "Find a hotel in Goa.",
        },
    )

    assert response.status_code == 422


@pytest.mark.integration
def test_delete_unknown_session_returns_404(
    client,
):
    response = client.delete(
        "/api/sessions/"
        + f"missing-{uuid4().hex}"
    )

    assert response.status_code == 404


@pytest.mark.integration
def test_delete_existing_session(
    client,
    stored_session_id,
):
    response = client.delete(
        f"/api/sessions/{stored_session_id}"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["deleted"] is True
    assert (
        body["session_id"]
        == stored_session_id
    )