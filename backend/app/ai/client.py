import os
from typing import Any

from dotenv import load_dotenv
from google import genai


load_dotenv(override=True)


def get_gemini_client() -> Any:
    """
    Create a Gemini client using GEMINI_API_KEY.
    """
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. "
            "Add it to the backend/.env file."
        )

    return genai.Client(
        api_key=api_key
    )


def get_model_name() -> str:
    """
    Return the configured Gemini model name.
    """
    return os.getenv(
        "GEMINI_MODEL",
        "gemini-3.6-flash",
    )


def ai_agent_enabled() -> bool:
    """
    Allow Phase 2 to be disabled without changing code.
    """
    return (
        os.getenv("USE_AI_AGENT", "true")
        .strip()
        .casefold()
        in {"true", "1", "yes", "on"}
    )


def get_max_agent_steps() -> int:
    """
    Prevent an infinite AI and tool-calling loop.
    """
    raw_value = os.getenv(
        "MAX_AGENT_STEPS",
        "6",
    )

    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        value = 6

    return max(1, min(value, 10))