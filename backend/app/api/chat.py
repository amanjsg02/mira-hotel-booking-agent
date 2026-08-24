import logging
import os

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    status,
)

from app.ai.client import (
    ai_agent_enabled,
    get_max_agent_steps,
    get_model_name,
)
from app.models import (
    ChatRequest,
    ChatResponse,
)
from app.repositories.hold_repository import (
    hold_repository,
)
from app.services.orchestrator import (
    handle_message,
)
from app.services.session_store import (
    session_store,
)


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api",
    tags=["Hotel Booking Agent"],
)


@router.delete(
    "/sessions/{session_id}",
)
def delete_conversation_session(
    session_id: str,
) -> dict:
    deleted_count = session_store.clear(
        session_id
    )

    if deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail="Conversation session not found.",
        )

    return {
        "deleted": True,
        "session_id": session_id,
    }

@router.post(
    "/chat",
    response_model=ChatResponse,
)
def chat(
    request: ChatRequest,
) -> ChatResponse:
    """
    Persist messages and provide idempotent processing.
    """
    existing_response = (
        session_store.get_processed_response(
            request.request_id
        )
    )

    if existing_response is not None:
        return existing_response

    try:
        session_store.get(
            request.session_id
        )

        session_store.save_message(
            session_id=request.session_id,
            role="guest",
            content=request.message,
        )

        response = handle_message(
            session_id=request.session_id,
            message=request.message,
        )

        response = response.model_copy(
            update={
                "request_id": request.request_id,
            }
        )

        session_store.save_message(
            session_id=request.session_id,
            role="agent",
            content=response.response,
        )

        session_store.save_tool_traces(
            session_id=request.session_id,
            traces=response.tool_traces,
        )

        session_store.save_processed_response(
            request_id=request.request_id,
            session_id=request.session_id,
            response=response,
        )

        return response

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception(
            "Unexpected chat request failure."
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "The booking agent encountered an "
                "unexpected error."
            ),
        ) from exc


@router.get(
    "/sessions/{session_id}",
)
def get_session(
    session_id: str,
):
    return {
        "session_id": session_id,
        "state": session_store.get(
            session_id
        ),
    }


@router.get(
    "/sessions/{session_id}/messages",
)
def get_session_messages(
    session_id: str,
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
):
    return {
        "session_id": session_id,
        "messages": session_store.get_messages(
            session_id=session_id,
            limit=limit,
        ),
    }


@router.get(
    "/sessions/{session_id}/tools",
)
def get_session_tools(
    session_id: str,
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
):
    return {
        "session_id": session_id,
        "tool_executions": (
            session_store.get_tool_traces(
                session_id=session_id,
                limit=limit,
            )
        ),
    }


@router.delete(
    "/sessions/{session_id}",
)
def delete_session(
    session_id: str,
):
    deleted_count = session_store.clear(
        session_id
    )

    return {
        "session_id": session_id,
        "deleted": deleted_count == 1,
    }


@router.get(
    "/holds/{hold_id}",
)
def get_hold(
    hold_id: str,
):
    hold = hold_repository.get(hold_id)

    if hold is None:
        raise HTTPException(
            status_code=404,
            detail="Booking hold not found.",
        )

    return hold


@router.get(
    "/sessions/{session_id}/holds",
)
def get_session_holds(
    session_id: str,
):
    return {
        "session_id": session_id,
        "holds": (
            hold_repository.list_for_session(
                session_id
            )
        ),
    }


@router.get(
    "/agent/status",
)
def get_agent_status():
    return {
        "phase": "phase4",
        "provider": "gemini",
        "model": get_model_name(),
        "ai_agent_enabled": (
            ai_agent_enabled()
        ),
        "api_key_configured": bool(
            os.getenv("GEMINI_API_KEY")
        ),
        "max_agent_steps": (
            get_max_agent_steps()
        ),
        "persistent_storage": "sqlite",
    }