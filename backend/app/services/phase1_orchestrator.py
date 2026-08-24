from typing import Any

from app.models import (
    ChatResponse,
    ToolTrace,
)
from app.services.extractor import (
    find_missing_required_fields,
    update_state_from_message,
)
from app.services.session_store import session_store
from app.tools.registry import execute_tool


# Questions asked when mandatory booking information is missing.
FOLLOW_UP_QUESTIONS: dict[str, str] = {
    "destination": (
        "Where would you like to stay?"
    ),
    "dates": (
        "What dates would you like to check in and check out?"
    ),
    "guests": (
        "How many adults and children will be travelling?"
    ),
}


CURRENCY_SYMBOLS: dict[str, str] = {
    "INR": "₹",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
}


POLICY_KEYWORDS: dict[str, list[str]] = {
    "cancellation": [
        "cancellation",
        "cancel",
        "refund",
        "refundable",
    ],
    "check_in": [
        "check in",
        "check-in",
        "checkin",
    ],
    "check_out": [
        "check out",
        "check-out",
        "checkout",
    ],
    "children_allowed": [
        "children allowed",
        "kids allowed",
        "child policy",
        "children policy",
    ],
    "pets_allowed": [
        "pets allowed",
        "pet friendly",
        "pet-friendly",
        "pet policy",
    ],
}


UNKNOWN_INFORMATION_KEYWORDS: dict[str, list[str]] = {
    "heated_pool": [
        "heated pool",
        "pool heated",
        "heated swimming pool",
    ],
}


def format_money(
    amount: int | float,
    currency: str = "INR",
) -> str:
    """
    Format a monetary amount using its currency.

    Examples:
        12000 INR -> ₹12,000
        250 USD   -> $250
    """
    symbol = CURRENCY_SYMBOLS.get(currency.upper())

    if symbol:
        return f"{symbol}{amount:,.0f}"

    return f"{currency.upper()} {amount:,.0f}"


def format_date(date_value: Any) -> str:
    """
    Format a date for a user-facing response.

    A safe fallback is used because tool data might occasionally
    contain ISO-formatted strings instead of date objects.
    """
    if hasattr(date_value, "strftime"):
        return date_value.strftime("%d %b %Y")

    return str(date_value)


def humanize(value: str) -> str:
    """
    Convert dataset keys into readable text.

    Example:
        private_pool -> private pool
    """
    return value.replace("_", " ")


def detect_policy_request(message: str) -> str | None:
    """
    Detect whether the guest is asking about a hotel policy.
    """
    normalized = message.casefold()

    for policy_name, keywords in POLICY_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return policy_name

    return None


def detect_unknown_information_request(
    message: str,
) -> str | None:
    """
    Detect questions about information that may not exist
    in the dataset.

    This is a small Phase 1 rule-based implementation.
    Phase 2 can use structured LLM extraction.
    """
    normalized = message.casefold()

    for information_name, keywords in (
        UNKNOWN_INFORMATION_KEYWORDS.items()
    ):
        if any(keyword in normalized for keyword in keywords):
            return information_name

    return None


def choose_follow_up_question(
    missing_fields: list[str],
) -> str:
    """
    Return one conversational follow-up question.

    Asking one question at a time keeps the interaction from
    feeling like a form.
    """
    first_missing_field = missing_fields[0]

    return FOLLOW_UP_QUESTIONS.get(
        first_missing_field,
        "Could you provide a little more information?",
    )


def call_tool(
    tool_name: str,
    arguments: dict[str, Any],
    traces: list[ToolTrace],
) -> Any:
    """
    Execute a registered tool and record an auditable trace.

    This records structured application activity, not private
    chain-of-thought.
    """
    try:
        result = execute_tool(
            tool_name=tool_name,
            arguments=arguments,
        )

        traces.append(
            ToolTrace(
                tool=tool_name,
                arguments=arguments,
                result=result,
                status="success",
            )
        )

        return result

    except Exception as exc:
        traces.append(
            ToolTrace(
                tool=tool_name,
                arguments=arguments,
                result={
                    "error": str(exc),
                },
                status="error",
            )
        )

        raise


def destination_is_supported(
    destination: str,
    supported_destinations: list[str],
) -> bool:
    """
    Compare destinations without depending on capitalization.
    """
    normalized_destination = destination.strip().casefold()

    return any(
        supported.strip().casefold()
        == normalized_destination
        for supported in supported_destinations
    )


def get_combined_amenities(
    search_result: dict[str, Any],
) -> list[str]:
    """
    Return combined property and room amenities.

    Supports both the old and updated search result format.
    """
    if search_result.get("combined_amenities"):
        return search_result["combined_amenities"]

    property_amenities = search_result.get(
        "property_amenities",
        [],
    )
    room_amenities = search_result.get(
        "room_amenities",
        [],
    )

    return sorted(
        set(property_amenities + room_amenities)
    )


def build_recommendation_response(
    recommendation: dict[str, Any],
    price: dict[str, Any],
) -> str:
    """
    Generate a grounded response using only tool results.
    """
    currency = price.get(
        "currency",
        recommendation.get("currency", "INR"),
    )

    amenities = get_combined_amenities(recommendation)

    readable_amenities = [
        humanize(amenity)
        for amenity in amenities[:5]
    ]

    if readable_amenities:
        amenity_text = ", ".join(readable_amenities)
        amenity_sentence = (
            f"Some available amenities are {amenity_text}. "
        )
    else:
        amenity_sentence = (
            "The dataset does not provide additional "
            "amenity information for this room. "
        )

    number_of_nights = price.get(
        "number_of_nights",
        price.get("nights"),
    )

    return (
        f"I found the {recommendation['room_name']} at "
        f"{recommendation['property_name']} in "
        f"{recommendation.get('area') or recommendation['city']}. "
        f"It accommodates up to "
        f"{recommendation['capacity']} guests and costs "
        f"{format_money(recommendation['price_per_night'], currency)} "
        f"per night. For {number_of_nights} "
        f"{'night' if number_of_nights == 1 else 'nights'}, "
        f"the room total is "
        f"{format_money(price['total'], currency)}. "
        f"{amenity_sentence}"
        "Would you like to see another option, check the "
        "cancellation policy, or continue toward booking?"
    )


def handle_policy_request(
    session_id: str,
    message: str,
    state: Any,
    traces: list[ToolTrace],
) -> ChatResponse | None:
    """
    Handle policy questions for the currently selected property.

    Returns None when the message is not a policy request.
    """
    requested_policy = detect_policy_request(message)

    if requested_policy is None:
        return None

    if not state.selected_property_id:
        return ChatResponse(
            session_id=session_id,
            response=(
                "I can check that policy after we select a "
                "property. Tell me your destination, dates and "
                "number of guests first."
            ),
            state=state,
            action="policy_requires_property",
            next_action="collect_booking_requirements",
            tool_traces=traces,
        )

    policy_result = call_tool(
        tool_name="get_policy",
        arguments={
            "property_id": state.selected_property_id,
            "policy_name": requested_policy,
        },
        traces=traces,
    )

    if not policy_result.get("known"):
        response = policy_result.get(
            "message",
            (
                "The available hotel data does not specify "
                "that policy."
            ),
        )

        return ChatResponse(
            session_id=session_id,
            response=response,
            state=state,
            action="unknown_policy_information",
            next_action="offer_other_help",
            tool_traces=traces,
        )

    property_name = policy_result["property_name"]
    readable_policy = humanize(
        policy_result["policy"]
    )
    policy_value = policy_result["value"]

    if isinstance(policy_value, bool):
        policy_text = "Yes" if policy_value else "No"
    else:
        policy_text = str(policy_value)

    return ChatResponse(
        session_id=session_id,
        response=(
            f"The {readable_policy} information for "
            f"{property_name} is: {policy_text}. "
            "Would you like to continue with this room or "
            "see another option?"
        ),
        state=state,
        action="provide_policy",
        next_action="continue_toward_booking",
        tool_traces=traces,
    )


def handle_unknown_information_request(
    session_id: str,
    message: str,
    state: Any,
    traces: list[ToolTrace],
) -> ChatResponse | None:
    """
    Handle questions such as 'Is the pool heated?'.

    Unknown fields must not be converted into false values.
    """
    requested_information = (
        detect_unknown_information_request(message)
    )

    if requested_information is None:
        return None

    if not state.selected_room_id:
        return ChatResponse(
            session_id=session_id,
            response=(
                "I can check that after we select a hotel. "
                "Please provide your destination, dates and "
                "number of guests first."
            ),
            state=state,
            action="information_requires_room",
            next_action="collect_booking_requirements",
            tool_traces=traces,
        )

    room_details = call_tool(
        tool_name="get_room_details",
        arguments={
            "room_id": state.selected_room_id,
        },
        traces=traces,
    )

    room = room_details.get("room", {})
    room_amenities = room.get("amenities", [])
    property_amenities = room_details.get(
        "property_amenities",
        [],
    )

    known_amenities = set(
        room_amenities + property_amenities
    )

    if requested_information in known_amenities:
        response = (
            f"Yes, the dataset lists "
            f"{humanize(requested_information)} for "
            f"{room_details['property_name']}."
        )
        action = "provide_known_information"
    else:
        response = (
            f"The available hotel data does not specify "
            f"whether the pool at "
            f"{room_details['property_name']} is heated. "
            "I don't want to assume or provide inaccurate "
            "information."
        )
        action = "unknown_information"

    return ChatResponse(
        session_id=session_id,
        response=(
            f"{response} Would you like to check another "
            "room or continue with this option?"
        ),
        state=state,
        action=action,
        next_action="offer_other_help",
        tool_traces=traces,
    )


def handle_message(
    session_id: str,
    message: str,
) -> ChatResponse:
    """
    Main Phase 1 booking-agent workflow.

    Workflow:
        1. Load existing state.
        2. Extract new information.
        3. Update and save state.
        4. Handle policy or information questions.
        5. Ask for missing required fields.
        6. Validate the destination.
        7. Search matching rooms.
        8. Check availability.
        9. Calculate deterministic pricing.
       10. Save selected property and room.
       11. Return response, state and tool traces.
    """
    traces: list[ToolTrace] = []

    # ---------------------------------------------------------
    # 1. Load previous conversation state
    # ---------------------------------------------------------
    current_state = session_store.get(session_id)

    # ---------------------------------------------------------
    # 2. Extract information and merge it with existing state
    # ---------------------------------------------------------
    state = update_state_from_message(
        current=current_state,
        message=message,
    )

    # Save immediately so partial information is not lost.
    session_store.save(session_id, state)

    # ---------------------------------------------------------
    # 3. Handle questions about the selected property
    # ---------------------------------------------------------
    policy_response = handle_policy_request(
        session_id=session_id,
        message=message,
        state=state,
        traces=traces,
    )

    if policy_response is not None:
        return policy_response

    unknown_information_response = (
        handle_unknown_information_request(
            session_id=session_id,
            message=message,
            state=state,
            traces=traces,
        )
    )

    if unknown_information_response is not None:
        return unknown_information_response

    # ---------------------------------------------------------
    # 4. Check mandatory booking information
    # ---------------------------------------------------------
    missing_fields = find_missing_required_fields(
        state
    )

    if missing_fields:
        question = choose_follow_up_question(
            missing_fields
        )

        return ChatResponse(
            session_id=session_id,
            response=question,
            state=state,
            action="ask_missing_information",
            next_action=f"collect_{missing_fields[0]}",
            tool_traces=traces,
        )

    guest_count = state.guests.total

    # This should already be covered by missing-field validation,
    # but the explicit check keeps the orchestrator safe.
    if guest_count is None or guest_count <= 0:
        return ChatResponse(
            session_id=session_id,
            response=(
                "Please tell me how many adults and children "
                "will be travelling."
            ),
            state=state,
            action="invalid_guest_count",
            next_action="collect_guests",
            tool_traces=traces,
        )

    # ---------------------------------------------------------
    # 5. Verify destination inventory
    # ---------------------------------------------------------
    supported_destinations = call_tool(
        tool_name="get_supported_destinations",
        arguments={},
        traces=traces,
    )

    if not destination_is_supported(
        destination=state.destination,
        supported_destinations=supported_destinations,
    ):
        available_destinations = ", ".join(
            supported_destinations
        )

        return ChatResponse(
            session_id=session_id,
            response=(
                f"I understood your destination as "
                f"{state.destination}, but I don't currently "
                f"have hotel inventory there. "
                f"My available destinations are "
                f"{available_destinations}. "
                "Would you like to try one of these?"
            ),
            state=state,
            action="unsupported_destination",
            next_action="ask_for_supported_destination",
            tool_traces=traces,
        )

    # ---------------------------------------------------------
    # 6. Search for matching properties and rooms
    # ---------------------------------------------------------
    search_arguments = {
        "destination": state.destination,
        "guest_count": guest_count,
        "budget_per_night": state.budget_per_night,
        "required_amenities": (
            state.preferred_amenities
        ),
    }

    search_results = call_tool(
        tool_name="search_properties",
        arguments=search_arguments,
        traces=traces,
    )

    if not search_results:
        requirement_parts: list[str] = []

        if state.budget_per_night is not None:
            requirement_parts.append(
                f"a budget of "
                f"{format_money(state.budget_per_night)} "
                f"per night"
            )

        if state.preferred_amenities:
            readable_requirements = ", ".join(
                humanize(amenity)
                for amenity in state.preferred_amenities
            )
            requirement_parts.append(
                f"the requested amenities "
                f"({readable_requirements})"
            )

        if requirement_parts:
            requirement_description = (
                " and ".join(requirement_parts)
            )

            response = (
                f"I couldn't find a room in "
                f"{state.destination} for {guest_count} guests "
                f"that matches {requirement_description}. "
                "Would you like to increase the budget or "
                "relax one of the amenity preferences?"
            )
        else:
            response = (
                f"I couldn't find a room in "
                f"{state.destination} that can accommodate "
                f"{guest_count} guests. Would you like to try "
                "another destination?"
            )

        return ChatResponse(
            session_id=session_id,
            response=response,
            state=state,
            action="no_matching_properties",
            next_action="ask_to_relax_constraints",
            tool_traces=traces,
        )

    # ---------------------------------------------------------
    # 7. Check availability for each matching room
    # ---------------------------------------------------------
    available_results: list[dict[str, Any]] = []

    for candidate in search_results:
        availability_arguments = {
            "room_id": candidate["room_id"],
            "check_in": state.check_in,
            "check_out": state.check_out,
        }

        availability_result = call_tool(
            tool_name="check_availability",
            arguments=availability_arguments,
            traces=traces,
        )

        if availability_result.get("available"):
            available_results.append(candidate)

    if not available_results:
        return ChatResponse(
            session_id=session_id,
            response=(
                f"I found rooms matching your requirements in "
                f"{state.destination}, but they are unavailable "
                f"from {format_date(state.check_in)} to "
                f"{format_date(state.check_out)}. "
                "Would you like to try different dates or "
                "relax one of your preferences?"
            ),
            state=state,
            action="matching_rooms_unavailable",
            next_action="ask_for_alternative_dates",
            tool_traces=traces,
        )

    # ---------------------------------------------------------
    # 8. Select the best available recommendation
    # ---------------------------------------------------------
    #
    # search_properties() already sorts results by nightly price,
    # so the first available result is currently the cheapest
    # room satisfying all hard requirements.
    recommendation = available_results[0]

    # ---------------------------------------------------------
    # 9. Calculate price using deterministic application logic
    # ---------------------------------------------------------
    price_arguments = {
        "room_id": recommendation["room_id"],
        "check_in": state.check_in,
        "check_out": state.check_out,
        "guest_count": guest_count,
        "selected_add_ons": [],
    }

    price_result = call_tool(
        tool_name="calculate_price",
        arguments=price_arguments,
        traces=traces,
    )

    # ---------------------------------------------------------
    # 10. Save selected recommendation in conversation state
    # ---------------------------------------------------------
    state.selected_property_id = recommendation[
        "property_id"
    ]
    state.selected_room_id = recommendation["room_id"]

    session_store.save(session_id, state)

    # ---------------------------------------------------------
    # 11. Build a grounded natural-language response
    # ---------------------------------------------------------
    response = build_recommendation_response(
        recommendation=recommendation,
        price=price_result,
    )

    return ChatResponse(
        session_id=session_id,
        response=response,
        state=state,
        action="recommend_room",
        next_action="offer_details_or_booking_hold",
        tool_traces=traces,
    )