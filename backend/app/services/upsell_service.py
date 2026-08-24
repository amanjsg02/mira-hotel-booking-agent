from app.models import (
    AddOnRecommendation,
    ConversationState,
)
from app.tools.hotel_tools import (
    get_room_details,
)


def get_relevant_add_ons(
    state: ConversationState,
) -> list[AddOnRecommendation]:
    """
    Recommend at most two relevant add-ons for the selected room.
    """
    if not state.selected_room_id:
        raise ValueError(
            "A room must be selected before suggesting add-ons."
        )

    details = get_room_details(
        state.selected_room_id
    )

    recommendations: list[
        AddOnRecommendation
    ] = []

    requirements_text = " ".join(
        state.special_requirements
    ).casefold()

    for add_on in details.get("add_ons", []):
        name = add_on["name"].casefold()
        reason: str | None = None

        if (
            state.guests.children > 0
            and "breakfast" in name
        ):
            reason = (
                "Breakfast may be convenient when "
                "travelling with children."
            )

        elif (
            "airport" in name
            and (
                "flight" in requirements_text
                or "airport" in requirements_text
            )
        ):
            reason = (
                "You mentioned travelling by flight."
            )

        elif (
            "late checkout" in name
            and "late" in requirements_text
        ):
            reason = (
                "You mentioned a late departure."
            )

        elif (
            "dinner" in name
            and state.guests.total == 2
        ):
            reason = (
                "This may be relevant for a couple's stay."
            )

        if reason:
            recommendations.append(
                AddOnRecommendation(
                    id=add_on["id"],
                    name=add_on["name"],
                    price=add_on["price"],
                    pricing_type=(
                        add_on["pricing_type"]
                    ),
                    reason=reason,
                )
            )

    return recommendations[:2]