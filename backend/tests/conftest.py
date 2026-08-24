from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.session_store import session_store


@pytest.fixture
def unique_session_id() -> str:
    """
    Return a unique session ID for every test.
    """
    return f"test-session-{uuid4().hex}"


@pytest.fixture
def unique_request_id() -> str:
    """
    Return a unique request ID for idempotency tests.
    """
    return f"test-request-{uuid4().hex}"


@pytest.fixture
def client() -> Generator[
    TestClient,
    None,
    None,
]:
    """
    Create a FastAPI test client.
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def stored_session_id() -> Generator[
    str,
    None,
    None,
]:
    """
    Create a temporary SQLite session and delete it
    after the test.
    """
    session_id = (
        f"stored-test-{uuid4().hex}"
    )

    session_store.get(session_id)

    yield session_id

    session_store.clear(session_id)