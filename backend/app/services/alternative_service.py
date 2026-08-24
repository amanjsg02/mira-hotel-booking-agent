from app.models import (
    ConversationState,
    RoomOption,
)
from app.services.recommendation_service import (
    find_ranked_recommendations,
)


def find_alternatives(
    state: ConversationState,
    mode: str = "relax_preferences",
) -> dict:
    """
    Find alternatives without silently relaxing hard constraints.

    Supported modes:
    - relax_preferences
    - increase_budget
    - cheapest
    """
    alternative_state = state.model_copy(
        deep=True
    )

    changed_constraints: list[str] = []

    if mode == "relax_preferences":
        alternative_state.preferred_amenities = []
        changed_constraints.append(
            "Removed optional preferences"
        )

    elif mode == "increase_budget":
        if alternative_state.budget_per_night:
            old_budget = (
                alternative_state.budget_per_night
            )

            alternative_state.budget_per_night = int(
                old_budget * 1.2
            )

            changed_constraints.append(
                f"Increased search budget from "
                f"₹{old_budget:,} to "
                f"₹{alternative_state.budget_per_night:,}"
            )

    elif mode == "cheapest":
        alternative_state.preferred_amenities = []
        alternative_state.budget_per_night = None

        changed_constraints.append(
            "Searched all prices while keeping capacity, "
            "dates and required amenities"
        )

    else:
        raise ValueError(
            f"Unsupported alternative mode: {mode}"
        )

    options = find_ranked_recommendations(
        alternative_state,
        limit=5,
    )

    if mode == "cheapest":
        options.sort(
            key=lambda option: (
                option.price_per_night
            )
        )

    return {
        "mode": mode,
        "changed_constraints": changed_constraints,
        "options": [
            option.model_dump(mode="json")
            for option in options
        ],
    }