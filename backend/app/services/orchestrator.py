from google.genai import types
import logging
from datetime import date
from typing import Any
from google.genai.errors import ClientError

from app.models import RoomOption
from app.services.alternative_service import (
    find_alternatives,
)
from app.services.recommendation_service import (
    find_ranked_recommendations,
)
from app.services.upsell_service import (
    get_relevant_add_ons,
)

from app.ai.client import (
    ai_agent_enabled,
    get_gemini_client,
    get_max_agent_steps,
    get_model_name,
)
from app.ai.prompts import build_agent_instructions

from app.models import (
    ChatResponse,
    ConversationState,
    ToolTrace,
)
from app.services.phase1_orchestrator import (
    handle_message as handle_phase1_message,
)
from app.services.session_store import session_store
from app.services.state_merger import (
    merge_state_update,
)
from app.tools.registry import execute_tool


logger = logging.getLogger(__name__)


AMENITY_CLASSIFICATION_INSTRUCTIONS = """
AMENITY CLASSIFICATION

Use required_amenities when the guest says an amenity is
mandatory, required, essential, must-have, non-negotiable,
or something they cannot compromise on.

Use preferred_amenities when the guest says preferred,
would be nice, ideally, optional, if possible, flexible,
or not mandatory.

"Not mandatory" always means preferred, not required.
Never place the same amenity in both lists.

Use canonical snake_case values such as private_pool,
swimming_pool, beach_access, breakfast, wifi, and parking.

Example:
Guest: "A private pool is mandatory."
Call update_booking_state with:
required_amenities=["private_pool"]
preferred_amenities=[]

Example:
Guest: "A private pool would be nice but is not mandatory."
Call update_booking_state with:
required_amenities=[]
preferred_amenities=["private_pool"]
"""


def json_safe(value: Any) -> Any:
    """
    Convert dates and model objects into JSON-safe values.
    """
    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, list):
        return [
            json_safe(item)
            for item in value
        ]

    if isinstance(value, dict):
        return {
            key: json_safe(item)
            for key, item in value.items()
        }

    if hasattr(value, "model_dump"):
        return json_safe(value.model_dump())

    return value


def convert_tool_arguments(
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """
    Convert Gemini JSON arguments into the Python types expected
    by Phase 1 tools.

    Gemini sends dates as YYYY-MM-DD strings. Hotel tools expect
    Python date objects.
    """
    converted = dict(arguments)

    tools_using_dates = {
    "check_availability",
    "calculate_price",
    "create_booking_hold",
}

    if tool_name in tools_using_dates:
        for field_name in [
            "check_in",
            "check_out",
        ]:
            value = converted.get(field_name)

            if value is None:
                raise ValueError(
                    f"{field_name} is required for "
                    f"{tool_name}."
                )

            if isinstance(value, str):
                try:
                    converted[field_name] = (
                        date.fromisoformat(value)
                    )
                except ValueError as exc:
                    raise ValueError(
                        f"{field_name} must use "
                        f"YYYY-MM-DD format."
                    ) from exc

            elif not isinstance(value, date):
                raise TypeError(
                    f"{field_name} must be a date "
                    f"or YYYY-MM-DD string."
                )

    return converted


def validate_tool_call_against_state(
    tool_name: str,
    arguments: dict[str, Any],
    state: ConversationState,
) -> None:
    """
    Validate required conversation state before executing a
    hotel tool.
    """

    if tool_name == "search_properties":
        destination = (
            arguments.get("destination")
            or state.destination
        )

        guest_count = (
            arguments.get("guest_count")
            or state.guests.total
        )

        if not destination:
            raise ValueError(
                "Destination is required before "
                "searching properties."
            )

        if guest_count is None:
            raise ValueError(
                "Guest count is required before "
                "searching properties."
            )

        if guest_count <= 0:
            raise ValueError(
                "Guest count must be greater than zero."
            )

    if tool_name in {
        "check_availability",
        "calculate_price",
    }:
        check_in = (
            arguments.get("check_in")
            or state.check_in
        )
        check_out = (
            arguments.get("check_out")
            or state.check_out
        )

        if not check_in or not check_out:
            raise ValueError(
                "Check-in and check-out dates are "
                "required for this tool."
            )

    if tool_name == "get_room_details":
        if not arguments.get("room_id"):
            raise ValueError(
                "room_id is required to retrieve "
                "room details."
            )

    if tool_name == "get_policy":
        property_id = (
            arguments.get("property_id")
            or state.selected_property_id
        )

        if not property_id:
            raise ValueError(
                "A property must be selected before "
                "retrieving its policy."
            )

    if tool_name == "calculate_price":
        guest_count = (
            arguments.get("guest_count")
            or state.guests.total
        )

        if guest_count is None or guest_count <= 0:
            raise ValueError(
                "A valid guest count is required "
                "before calculating price."
            )


def execute_agent_tool(
    session_id: str,
    tool_name: str,
    arguments: dict[str, Any] | None,
    traces: list[ToolTrace],
) -> Any:
    """
    Execute a Phase 2 state-update tool or an approved Phase 1
    hotel tool.

    Errors are returned as structured results so Gemini can
    recover or ask the guest for clarification.
    """

    allowed_tools = {
    "update_booking_state",
    "get_supported_destinations",
    "search_properties",
    "check_availability",
    "get_room_details",
    "get_policy",
    "calculate_price",
    "find_recommendations",
    "find_alternatives",
    "get_next_option",
    "select_option",
    "get_relevant_add_ons",
    "create_booking_hold",
    "get_booking_hold",
    "cancel_booking_hold",
}

    arguments = arguments or {}

    try:
        # -----------------------------------------------------
        # 1. Reject tools that are not explicitly approved
        # -----------------------------------------------------
        if tool_name not in allowed_tools:
            raise ValueError(
                f"Tool '{tool_name}' is not allowed."
            )

        # -----------------------------------------------------
        # 2. Handle the Phase 2 state-update tool
        # -----------------------------------------------------
        if tool_name == "update_booking_state":
            current_state = session_store.get(
                session_id
            )

            # Remove null values because null means that Gemini
            # did not extract a new value for that field.
            #
            # Existing values must remain unchanged.
            cleaned_update = {
                key: value
                for key, value in arguments.items()
                if value is not None
            }

            if not cleaned_update:
                result = {
                    "updated": False,
                    "message": (
                        "No new booking information "
                        "was provided."
                    ),
                    "state": current_state.model_dump(
                        mode="json"
                    ),
                }

            else:
                updated_state = merge_state_update(
                    current=current_state,
                    update=cleaned_update,
                )

                saved_state = session_store.save(
                    session_id,
                    updated_state,
                )

                result = {
                    "updated": True,
                    "changed_fields": list(
                        cleaned_update.keys()
                    ),
                    "state": saved_state.model_dump(
                        mode="json"
                    ),
                }
        elif tool_name == "find_recommendations":
            current_state = session_store.get(
                session_id
            )

            options = find_ranked_recommendations(
                current_state
            )

            current_state.last_search_results = options
            current_state.current_option_index = (
                0 if options else None
            )

            if options:
                current_state.selected_property_id = (
                    options[0].property_id
                )
                current_state.selected_room_id = (
                    options[0].room_id
                )

            current_state.last_agent_action = (
                "recommend_options"
            )

            session_store.save(
                session_id,
                current_state,
            )

            result = {
                "count": len(options),
                "options": [
                    option.model_dump(mode="json")
                    for option in options
                ],
            }


        elif tool_name == "find_alternatives":
            current_state = session_store.get(
                session_id
            )

            mode = arguments.get(
                "mode",
                "relax_preferences",
            )

            result = find_alternatives(
                state=current_state,
                mode=mode,
            )

            options = [
                RoomOption.model_validate(option)
                for option in result["options"]
            ]

            current_state.last_search_results = options
            current_state.current_option_index = (
                0 if options else None
            )

            if options:
                current_state.selected_property_id = (
                    options[0].property_id
                )
                current_state.selected_room_id = (
                    options[0].room_id
                )

            session_store.save(
                session_id,
                current_state,
            )


        elif tool_name == "get_next_option":
            current_state = session_store.get(
                session_id
            )

            options = current_state.last_search_results

            if not options:
                raise ValueError(
                    "There are no saved recommendations."
                )

            current_index = (
                current_state.current_option_index
                if current_state.current_option_index
                is not None
                else 0
            )

            next_index = current_index + 1

            if next_index >= len(options):
                raise ValueError(
                    "There are no more saved options."
                )

            option = options[next_index]

            current_state.current_option_index = (
                next_index
            )
            current_state.selected_property_id = (
                option.property_id
            )
            current_state.selected_room_id = (
                option.room_id
            )

            session_store.save(
                session_id,
                current_state,
            )

            result = {
                "option_index": next_index,
                "option": option.model_dump(
                    mode="json"
                ),
            }


        elif tool_name == "select_option":
            current_state = session_store.get(
                session_id
            )

            option_number = arguments.get(
                "option_number"
            )

            if option_number is None:
                raise ValueError(
                    "option_number is required."
                )

            option_index = option_number - 1

            if (
                option_index < 0
                or option_index
                >= len(current_state.last_search_results)
            ):
                raise ValueError(
                    "Invalid option number."
                )

            option = current_state.last_search_results[
                option_index
            ]

            current_state.current_option_index = (
                option_index
            )
            current_state.selected_property_id = (
                option.property_id
            )
            current_state.selected_room_id = (
                option.room_id
            )
            current_state.pending_confirmation = None

            session_store.save(
                session_id,
                current_state,
            )

            result = {
                "selected": True,
                "option": option.model_dump(
                    mode="json"
                ),
            }


        elif tool_name == "get_relevant_add_ons":
            current_state = session_store.get(
                session_id
            )

            recommendations = get_relevant_add_ons(
                current_state
            )

            current_state.suggested_add_ons = (
                recommendations
            )

            session_store.save(
                session_id,
                current_state,
            )

            result = {
                "add_ons": [
                    item.model_dump(mode="json")
                    for item in recommendations
                ]
            }


        
    # Keep your existing registry execution here.
        # -----------------------------------------------------
        # 3. Handle registered hotel tools
        # -----------------------------------------------------
        else:
            current_state = session_store.get(
                session_id
            )

            validate_tool_call_against_state(
                tool_name=tool_name,
                arguments=arguments,
                state=current_state,
            )

            converted_arguments = (
                convert_tool_arguments(
                    tool_name=tool_name,
                    arguments=arguments,
                )
            )

            result = execute_tool(
                tool_name=tool_name,
                arguments=converted_arguments,
            )

            # Remember the room inspected through get_room_details.
            if (
                tool_name == "get_room_details"
                and isinstance(result, dict)
                and result.get("room")
            ):
                current_state.selected_property_id = (
                    result.get("property_id")
                )
                current_state.selected_room_id = (
                    result["room"].get("id")
                )

                session_store.save(
                    session_id,
                    current_state,
                )

            # Remember the selected room after calculating price.
            if (
                tool_name == "calculate_price"
                and isinstance(result, dict)
                and result.get("room_id")
            ):
                current_state.selected_property_id = (
                    result.get("property_id")
                )
                current_state.selected_room_id = (
                    result.get("room_id")
                )

                session_store.save(
                    session_id,
                    current_state,
                )

            # ADD THE BOOKING-HOLD CODE HERE.
            if (
                tool_name == "create_booking_hold"
                and isinstance(result, dict)
                and result.get("hold_id")
            ):
                current_state.active_hold_id = (
                    result["hold_id"]
                )
                current_state.pending_confirmation = None
                current_state.last_agent_action = (
                    "booking_hold_created"
                )

                session_store.save(
                    session_id,
                    current_state,
                )

        # This stays after the complete if/elif/else section.
        safe_result = json_safe(result)

        traces.append(
            ToolTrace(
                tool=tool_name,
                arguments=json_safe(arguments),
                result=safe_result,
                status="success",
            )
        )

        return safe_result

    except Exception as exc:
        # Return the error to Gemini instead of crashing the
        # complete conversation. Gemini can then ask for missing
        # information or choose a different tool.
        error_result = {
            "success": False,
            "tool": tool_name,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }

        traces.append(
            ToolTrace(
                tool=tool_name,
                arguments=json_safe(arguments),
                result=error_result,
                status="error",
            )
        )

        return error_result

def determine_action(
    traces: list[ToolTrace],
) -> tuple[str, str]:
    """
    Produce frontend-friendly structured actions from the
    observable tool trace.
    """
    if not traces:
        return (
            "respond_or_ask_question",
            "await_guest_response",
        )

    successful_tools = [
        trace.tool
        for trace in traces
        if trace.status == "success"
    ]

    if "calculate_price" in successful_tools:
        return (
            "recommend_priced_room",
            "offer_booking_or_alternative",
        )

    if "get_policy" in successful_tools:
        return (
            "provide_policy",
            "continue_toward_booking",
        )

    if "get_room_details" in successful_tools:
        return (
            "provide_room_details",
            "continue_toward_booking",
        )

    if "check_availability" in successful_tools:
        return (
            "check_availability",
            "recommend_or_search_alternative",
        )

    if "search_properties" in successful_tools:
        return (
            "search_properties",
            "check_availability",
        )

    if "update_booking_state" in successful_tools:
        return (
            "update_state",
            "collect_missing_information_or_search",
        )

    return (
        "tool_execution",
        "continue_conversation",
    )


def build_gemini_tools(
    session_id: str,
    traces: list[ToolTrace],
):
    """
    Create Gemini-callable functions for one conversation.

    Gemini automatically:
    1. Selects a function.
    2. Generates its arguments.
    3. Calls the Python function.
    4. Receives the result.
    5. Continues until it produces a final response.
    """

    def update_booking_state(
        destination: str | None = None,
        check_in: str | None = None,
        check_out: str | None = None,
        adults: int | None = None,
        children: int | None = None,
        budget_per_night: int | None = None,
        required_amenities: list[str] | None = None,
        preferred_amenities: list[str] | None = None,
        special_requirements: list[str] | None = None,
    ) -> dict:
        """
        Update booking information extracted from the latest
        guest message.

        Only provide values explicitly stated or clearly implied
        by the guest. Leave other values as null.

        Args:
            destination: Requested destination or city.
            check_in: Check-in date in YYYY-MM-DD format.
            check_out: Check-out date in YYYY-MM-DD format.
            adults: Number of adults.
            children: Number of children.
            budget_per_night: Maximum nightly budget in INR.
            required_amenities: Hard requirements explicitly
                described as mandatory, required, essential,
                must-have, or non-negotiable.
            preferred_amenities: Optional preferences described
                as nice to have, preferred, ideal, flexible,
                if possible, or not mandatory.
            special_requirements: Other guest requirements.

        Returns:
            The updated booking state.
        """
        arguments = {
            "destination": destination,
            "check_in": check_in,
            "check_out": check_out,
            "adults": adults,
            "children": children,
            "budget_per_night": budget_per_night,
            "required_amenities": required_amenities,
            "preferred_amenities": preferred_amenities,
            "special_requirements": special_requirements,
        }

        return execute_agent_tool(
            session_id=session_id,
            tool_name="update_booking_state",
            arguments=arguments,
            traces=traces,
        )

    def get_supported_destinations() -> list[str]:
        """
        Return all destinations for which hotel inventory exists.

        Use this before searching to ensure that the requested
        destination is supported.
        """
        return execute_agent_tool(
            session_id=session_id,
            tool_name="get_supported_destinations",
            arguments={},
            traces=traces,
        )

    def search_properties(
        destination: str,
        guest_count: int,
        budget_per_night: int | None = None,
        required_amenities: list[str] | None = None,
    ) -> list:
        """
        Search rooms that satisfy destination, guest capacity,
        nightly budget and required amenities.

        This function does not confirm availability.

        Args:
            destination: Requested city or destination.
            guest_count: Total adults plus children.
            budget_per_night: Maximum nightly room budget.
            required_amenities: Amenities required by the guest.

        Returns:
            Matching properties and room types.
        """
        arguments = {
            "destination": destination,
            "guest_count": guest_count,
            "budget_per_night": budget_per_night,
            "required_amenities": (
                required_amenities or []
            ),
        }

        return execute_agent_tool(
            session_id=session_id,
            tool_name="search_properties",
            arguments=arguments,
            traces=traces,
        )

    def check_availability(
        room_id: str,
        check_in: str,
        check_out: str,
    ) -> dict:
        """
        Check whether a room type is available for requested dates.

        Search results alone do not guarantee availability.

        Args:
            room_id: Dataset room identifier.
            check_in: Check-in date in YYYY-MM-DD format.
            check_out: Check-out date in YYYY-MM-DD format.

        Returns:
            Availability status for the requested room and dates.
        """
        arguments = {
            "room_id": room_id,
            "check_in": check_in,
            "check_out": check_out,
        }

        return execute_agent_tool(
            session_id=session_id,
            tool_name="check_availability",
            arguments=arguments,
            traces=traces,
        )

    def get_room_details(
        room_id: str,
    ) -> dict:
        """
        Get factual room and property information.

        Use this for questions about amenities, capacity,
        policies or add-ons. If a requested field is absent,
        report that it is unknown.

        Args:
            room_id: Dataset room identifier.

        Returns:
            Grounded property and room information.
        """
        return execute_agent_tool(
            session_id=session_id,
            tool_name="get_room_details",
            arguments={
                "room_id": room_id,
            },
            traces=traces,
        )

    def get_policy(
        property_id: str,
        policy_name: str | None = None,
    ) -> dict:
        """
        Get one policy or all known policies for a property.

        Args:
            property_id: Dataset property identifier.
            policy_name: Requested policy, such as cancellation,
                check_in, check_out or pets_allowed.

        Returns:
            Known policy information or known=false when absent.
        """
        return execute_agent_tool(
            session_id=session_id,
            tool_name="get_policy",
            arguments={
                "property_id": property_id,
                "policy_name": policy_name,
            },
            traces=traces,
        )

    def calculate_price(
        room_id: str,
        check_in: str,
        check_out: str,
        guest_count: int,
        selected_add_ons: list[str] | None = None,
    ) -> dict:
        """
        Calculate the deterministic total booking price.

        Always use this function instead of calculating prices
        in the model response.

        Args:
            room_id: Dataset room identifier.
            check_in: Check-in date in YYYY-MM-DD format.
            check_out: Check-out date in YYYY-MM-DD format.
            guest_count: Total adults plus children.
            selected_add_ons: IDs of selected optional add-ons.

        Returns:
            Deterministic room subtotal, add-on total and final
            booking total.
        """
        arguments = {
            "room_id": room_id,
            "check_in": check_in,
            "check_out": check_out,
            "guest_count": guest_count,
            "selected_add_ons": (
                selected_add_ons or []
            ),
        }

        return execute_agent_tool(
            session_id=session_id,
            tool_name="calculate_price",
            arguments=arguments,
            traces=traces,
        )

    def find_recommendations() -> dict:
        """
        Find, validate, price and rank the best available rooms
        using the current conversation state.
        """
        return execute_agent_tool(
            session_id=session_id,
            tool_name="find_recommendations",
            arguments={},
            traces=traces,
        )


    def find_alternative_options(
        mode: str,
    ) -> dict:
        """
        Find alternative rooms.

        Args:
            mode: One of relax_preferences, increase_budget or
                cheapest.

        Returns:
            Alternative rooms and the constraints changed.
        """
        return execute_agent_tool(
            session_id=session_id,
            tool_name="find_alternatives",
            arguments={
                "mode": mode,
            },
            traces=traces,
        )


    def get_next_option() -> dict:
        """
        Return the next saved room when the guest says things like
        'the other one' or 'show me another option'.
        """
        return execute_agent_tool(
            session_id=session_id,
            tool_name="get_next_option",
            arguments={},
            traces=traces,
        )


    def select_option(
        option_number: int,
    ) -> dict:
        """
        Select one previously recommended room.

        Args:
            option_number: Human-facing option number starting at 1.

        Returns:
            The selected room.
        """
        return execute_agent_tool(
            session_id=session_id,
            tool_name="select_option",
            arguments={
                "option_number": option_number,
            },
            traces=traces,
        )


    def suggest_relevant_add_ons() -> dict:
        """
        Suggest at most two relevant add-ons for the selected room.
        """
        return execute_agent_tool(
            session_id=session_id,
            tool_name="get_relevant_add_ons",
            arguments={},
            traces=traces,
        )


    def create_booking_hold(
        room_id: str,
        check_in: str,
        check_out: str,
        guest_count: int,
        selected_add_ons: list[str] | None = None,
    ) -> dict:
        """
        Create a temporary booking hold after explicit guest
        confirmation.

        Never call this immediately after recommending a room.
        First show the final summary and obtain clear confirmation.

        Args:
            room_id: Selected room ID.
            check_in: YYYY-MM-DD.
            check_out: YYYY-MM-DD.
            guest_count: Total guest count.
            selected_add_ons: Confirmed add-on IDs.

        Returns:
            Temporary hold information.
        """
        return execute_agent_tool(
            session_id=session_id,
            tool_name="create_booking_hold",
            arguments={
                "session_id": session_id,
                "room_id": room_id,
                "check_in": check_in,
                "check_out": check_out,
                "guest_count": guest_count,
                "selected_add_ons": (
                    selected_add_ons or []
                ),
            },
            traces=traces,
        )

    return [
    update_booking_state,
    get_supported_destinations,
    search_properties,
    check_availability,
    get_room_details,
    get_policy,
    calculate_price,

    # Phase 3 tools
    find_recommendations,
    find_alternative_options,
    get_next_option,
    select_option,
    suggest_relevant_add_ons,
    create_booking_hold,
]

def run_ai_agent(
    session_id: str,
    message: str,
) -> ChatResponse:
    """
    Run the Phase 2 agent using Gemini automatic
    function calling.
    """
    client = get_gemini_client()

    current_state = session_store.get(
        session_id
    )

    traces: list[ToolTrace] = []

    instructions = build_agent_instructions(
        current_state
    )

    instructions = (
        instructions
        + "\n\n"
        + AMENITY_CLASSIFICATION_INSTRUCTIONS
    )

    gemini_tools = build_gemini_tools(
        session_id=session_id,
        traces=traces,
    )

    config = types.GenerateContentConfig(
        system_instruction=instructions,
        tools=gemini_tools,
        automatic_function_calling=(
            types.AutomaticFunctionCallingConfig(
                disable=False,
            )
        ),
    )

    chat = client.chats.create(
        model=get_model_name(),
        config=config,
    )

    response = chat.send_message(message)

    final_text = (
        response.text.strip()
        if response.text
        else ""
    )

    if not final_text:
        final_text = (
            "I couldn't complete that request safely. "
            "Could you clarify your destination, dates "
            "and number of guests?"
        )

    final_state = session_store.get(
        session_id
    )

    action, next_action = determine_action(
        traces
    )

    return ChatResponse(
        session_id=session_id,
        response=final_text,
        state=final_state,
        action=action,
        next_action=next_action,
        tool_traces=traces,
    )

def handle_message(
    session_id: str,
    message: str,
) -> ChatResponse:
    """
    Run Gemini and handle provider failures clearly.
    """
    if not ai_agent_enabled():
        response = handle_phase1_message(
            session_id=session_id,
            message=message,
        )

        return response.model_copy(
            update={
                "agent_mode": "phase1",
                "model_name": None,
            }
        )

    try:
        response = run_ai_agent(
            session_id=session_id,
            message=message,
        )

        return response.model_copy(
            update={
                "agent_mode": "phase2",
                "model_name": get_model_name(),
            }
        )

    except ClientError as exc:
        logger.exception(
            "Gemini API request failed."
        )

        current_state = session_store.get(
            session_id
        )

        status_code = getattr(
            exc,
            "code",
            getattr(
                exc,
                "status_code",
                None,
            ),
        )

        if status_code == 429:
            return ChatResponse(
                session_id=session_id,
                response=(
                    "The AI service has temporarily "
                    "reached its request limit. Your "
                    "booking details are saved. Please "
                    "try again shortly."
                ),
                state=current_state,
                action="ai_quota_exceeded",
                next_action=(
                    "retry_after_rate_limit"
                ),
                tool_traces=[],
                agent_mode="phase2",
                model_name=get_model_name(),
            )

        if status_code in {401, 403}:
            return ChatResponse(
                session_id=session_id,
                response=(
                    "The AI service is temporarily "
                    "unavailable because of a "
                    "configuration problem. Your "
                    "booking details are saved."
                ),
                state=current_state,
                action="ai_authentication_error",
                next_action="contact_support",
                tool_traces=[],
                agent_mode="phase2",
                model_name=get_model_name(),
            )

        return ChatResponse(
            session_id=session_id,
            response=(
                "The AI service is temporarily "
                "unavailable. Your booking details "
                "are saved. Please try again."
            ),
            state=current_state,
            action="ai_provider_error",
            next_action="retry",
            tool_traces=[],
            agent_mode="phase2",
            model_name=get_model_name(),
        )

    except Exception:
        logger.exception(
            "Unexpected Phase 2 agent failure."
        )

        current_state = session_store.get(
            session_id
        )

        return ChatResponse(
            session_id=session_id,
            response=(
                "I encountered an unexpected problem. "
                "Your previous booking information is "
                "still saved. Please try again."
            ),
            state=current_state,
            action="agent_error",
            next_action="retry",
            tool_traces=[],
            agent_mode="phase2",
            model_name=get_model_name(),
        )