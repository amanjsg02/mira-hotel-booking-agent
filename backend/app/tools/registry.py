from collections.abc import Callable
from typing import Any

from app.tools.hotel_tools import (
    calculate_price,
    cancel_booking_hold,
    check_availability,
    create_booking_hold,
    get_booking_hold,
    get_policy,
    get_room_details,
    get_supported_destinations,
    search_properties,
)


# Central registry containing every tool available to the agent.
#
# The orchestrator or LLM should call tools through this registry
# instead of directly importing individual tool functions.
TOOLS: dict[str, Callable[..., Any]] = {
    "get_supported_destinations": (
        get_supported_destinations
    ),
    "search_properties": search_properties,
    "check_availability": check_availability,
    "get_room_details": get_room_details,
    "get_policy": get_policy,
    "calculate_price": calculate_price,
    "create_booking_hold": create_booking_hold,
    "get_booking_hold": get_booking_hold,
    "cancel_booking_hold": cancel_booking_hold,
}

def get_available_tools() -> list[str]:
    """
    Return the names of all tools currently registered.

    This is useful for:
    - Debugging
    - API visibility
    - Testing
    - Building LLM tool definitions later
    """
    return sorted(TOOLS.keys())


def is_tool_registered(tool_name: str) -> bool:
    """
    Check whether a tool exists without executing it.
    """
    return tool_name in TOOLS


def execute_tool(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> Any:
    """
    Find and execute a registered tool.

    Args:
        tool_name:
            Name of the tool to execute.

        arguments:
            Keyword arguments passed to the tool function.

    Returns:
        The value returned by the tool.

    Raises:
        ValueError:
            If the requested tool is not registered.

        TypeError:
            If required arguments are missing or invalid.

        Exception:
            Any tool-specific exception is allowed to propagate
            so the orchestrator can record the failure.
    """
    arguments = arguments or {}

    tool = TOOLS.get(tool_name)

    if tool is None:
        available_tools = ", ".join(get_available_tools())

        raise ValueError(
            f"Unknown tool '{tool_name}'. "
            f"Available tools: {available_tools}"
        )

    try:
        return tool(**arguments)

    except TypeError as exc:
        raise TypeError(
            f"Invalid arguments for tool '{tool_name}': {exc}"
        ) from exc