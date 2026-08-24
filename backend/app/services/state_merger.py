from datetime import date

from pydantic import ValidationError

from app.models import ConversationState


def parse_iso_date(
    value: str | date | None,
) -> date | None:
    """
    Convert YYYY-MM-DD into a Python date.

    Existing Python date values are returned unchanged.
    """
    if value is None:
        return None

    if isinstance(value, date):
        return value

    if not isinstance(value, str):
        raise TypeError(
            "Date value must be a YYYY-MM-DD string."
        )

    try:
        return date.fromisoformat(value)

    except ValueError as exc:
        raise ValueError(
            f"Invalid date '{value}'. "
            "Expected YYYY-MM-DD."
        ) from exc


def clear_recommendations(
    state: ConversationState,
) -> None:
    """
    Clear recommendations and selections after a search-related
    requirement changes.

    Old recommendations may no longer be valid after destination,
    dates, guests, budget or amenities change.
    """
    state.last_search_results = []
    state.current_option_index = None

    state.selected_property_id = None
    state.selected_room_id = None

    state.selected_add_ons = []
    state.suggested_add_ons = []

    state.pending_confirmation = None
    state.active_hold_id = None


def normalize_list(
    values: list[str] | None,
) -> list[str] | None:
    """
    Normalize an LLM-provided string list.

    Null means the field was not mentioned and should not change.
    """
    if values is None:
        return None

    if not isinstance(values, list):
        raise TypeError(
            "Expected a list of strings."
        )

    normalized_values: list[str] = []
    seen: set[str] = set()

    for value in values:
        if not isinstance(value, str):
            raise TypeError(
                "Every list item must be a string."
            )

        normalized = (
            value.strip()
            .casefold()
            .replace("-", "_")
            .replace(" ", "_")
        )

        if normalized and normalized not in seen:
            seen.add(normalized)
            normalized_values.append(normalized)

    return normalized_values


def merge_state_update(
    current: ConversationState,
    update: dict,
) -> ConversationState:
    """
    Safely merge an LLM-proposed update into existing state.

    Rules:
    - Missing or null fields preserve existing values.
    - Only supplied values are updated.
    - Search-related changes invalidate old recommendations.
    - Check-out must be after check-in.
    - The final state is validated through ConversationState.
    """
    if not isinstance(update, dict):
        raise TypeError(
            "State update must be a dictionary."
        )

    state = current.model_copy(deep=True)

    # Track whether old search results must be cleared.
    search_requirements_changed = False

    # ---------------------------------------------------------
    # 1. Destination
    # ---------------------------------------------------------
    destination = update.get("destination")

    if destination is not None:
        if not isinstance(destination, str):
            raise TypeError(
                "Destination must be a string."
            )

        normalized_destination = destination.strip()

        if not normalized_destination:
            raise ValueError(
                "Destination cannot be empty."
            )

        normalized_destination = (
            normalized_destination.title()
        )

        if (
            state.destination
            != normalized_destination
        ):
            state.destination = (
                normalized_destination
            )
            search_requirements_changed = True

    # ---------------------------------------------------------
    # 2. Dates
    # ---------------------------------------------------------
    proposed_check_in = parse_iso_date(
        update.get("check_in")
    )

    proposed_check_out = parse_iso_date(
        update.get("check_out")
    )

    if proposed_check_in is not None:
        if state.check_in != proposed_check_in:
            state.check_in = proposed_check_in
            search_requirements_changed = True

    if proposed_check_out is not None:
        if state.check_out != proposed_check_out:
            state.check_out = proposed_check_out
            search_requirements_changed = True

    # ---------------------------------------------------------
    # 3. Guest composition
    # ---------------------------------------------------------
    adults = update.get("adults")
    children = update.get("children")

    if adults is not None:
        if not isinstance(adults, int):
            raise TypeError(
                "Adults must be an integer."
            )

        if adults < 1:
            raise ValueError(
                "At least one adult is required."
            )

        if state.guests.adults != adults:
            state.guests.adults = adults
            search_requirements_changed = True

    if children is not None:
        if not isinstance(children, int):
            raise TypeError(
                "Children must be an integer."
            )

        if children < 0:
            raise ValueError(
                "Children cannot be negative."
            )

        if state.guests.children != children:
            state.guests.children = children
            search_requirements_changed = True

    # ---------------------------------------------------------
    # 4. Nightly budget
    # ---------------------------------------------------------
    budget = update.get("budget_per_night")

    if budget is not None:
        if not isinstance(budget, int):
            raise TypeError(
                "Budget must be an integer."
            )

        if budget < 0:
            raise ValueError(
                "Budget cannot be negative."
            )

        if state.budget_per_night != budget:
            state.budget_per_night = budget
            search_requirements_changed = True

    # ---------------------------------------------------------
    # 5. Required amenities
    # ---------------------------------------------------------
    required_amenities = normalize_list(
        update.get("required_amenities")
    )

    if required_amenities is not None:
        if (
            state.required_amenities
            != required_amenities
        ):
            state.required_amenities = (
                required_amenities
            )
            search_requirements_changed = True

    # ---------------------------------------------------------
    # 6. Preferred amenities
    # ---------------------------------------------------------
    preferred_amenities = normalize_list(
        update.get("preferred_amenities")
    )

    if preferred_amenities is not None:
        if (
            state.preferred_amenities
            != preferred_amenities
        ):
            state.preferred_amenities = (
                preferred_amenities
            )
            search_requirements_changed = True

    # ---------------------------------------------------------
    # 7. Special requirements
    # ---------------------------------------------------------
    special_requirements = normalize_list(
        update.get("special_requirements")
    )

    if special_requirements is not None:
        if (
            state.special_requirements
            != special_requirements
        ):
            state.special_requirements = (
                special_requirements
            )

            # Special requirements do not necessarily invalidate
            # a hotel search, but they can change upsell results.
            state.suggested_add_ons = []

    # ---------------------------------------------------------
    # 8. Validate the complete date range
    # ---------------------------------------------------------
    if (
        state.check_in is not None
        and state.check_out is not None
        and state.check_out <= state.check_in
    ):
        raise ValueError(
            "Check-out must be after check-in."
        )

    # ---------------------------------------------------------
    # 9. Clear old recommendations only once
    # ---------------------------------------------------------
    if search_requirements_changed:
        clear_recommendations(state)

    # ---------------------------------------------------------
    # 10. Validate the final state
    # ---------------------------------------------------------
    try:
        return ConversationState.model_validate(
            state.model_dump()
        )

    except ValidationError as exc:
        raise ValueError(
            f"Invalid state update: {exc}"
        ) from exc