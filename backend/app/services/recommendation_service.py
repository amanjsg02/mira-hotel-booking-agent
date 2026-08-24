from typing import Any

from app.models import (
    ConversationState,
    RoomOption,
)
from app.tools.hotel_tools import (
    calculate_price,
    check_availability,
    search_properties,
)


def calculate_recommendation_score(
    candidate: dict[str, Any],
    state: ConversationState,
) -> tuple[float, list[str]]:
    """
    Deterministically score one available room.
    """
    score = 0.0
    reasons: list[str] = []

    amenities = set(
        candidate.get(
            "combined_amenities",
            [],
        )
    )

    guest_count = state.guests.total or 0

    for amenity in state.required_amenities:
        if amenity in amenities:
            score += 25
            reasons.append(
                f"Includes required "
                f"{amenity.replace('_', ' ')}"
            )

    for amenity in state.preferred_amenities:
        if amenity in amenities:
            score += 15
            reasons.append(
                f"Matches preferred "
                f"{amenity.replace('_', ' ')}"
            )

    if state.budget_per_night is not None:
        if (
            candidate["price_per_night"]
            <= state.budget_per_night
        ):
            score += 20
            reasons.append(
                "Within the nightly budget"
            )

    if candidate["capacity"] == guest_count:
        score += 10
        reasons.append(
            "Exact guest-capacity match"
        )
    elif candidate["capacity"] > guest_count:
        score += 5
        reasons.append(
            "Has extra guest capacity"
        )

    if "breakfast_included" in amenities:
        score += 5
        reasons.append(
            "Breakfast is included"
        )

    return score, reasons


def find_ranked_recommendations(
    state: ConversationState,
    limit: int = 3,
) -> list[RoomOption]:
    """
    Search, validate availability, calculate prices and rank
    available rooms.
    """
    if not state.destination:
        raise ValueError(
            "Destination is required."
        )

    if not state.check_in or not state.check_out:
        raise ValueError(
            "Check-in and check-out are required."
        )

    guest_count = state.guests.total

    if guest_count is None:
        raise ValueError(
            "Guest count is required."
        )

    candidates = search_properties(
        destination=state.destination,
        guest_count=guest_count,
        budget_per_night=state.budget_per_night,
        required_amenities=state.required_amenities,
    )

    options: list[RoomOption] = []

    for candidate in candidates:
        availability = check_availability(
            room_id=candidate["room_id"],
            check_in=state.check_in,
            check_out=state.check_out,
        )

        if not availability["available"]:
            continue

        pricing = calculate_price(
            room_id=candidate["room_id"],
            check_in=state.check_in,
            check_out=state.check_out,
            guest_count=guest_count,
            selected_add_ons=[],
        )

        score, reasons = (
            calculate_recommendation_score(
                candidate=candidate,
                state=state,
            )
        )

        options.append(
            RoomOption(
                property_id=(
                    candidate["property_id"]
                ),
                property_name=(
                    candidate["property_name"]
                ),
                room_id=candidate["room_id"],
                room_name=candidate["room_name"],
                city=candidate["city"],
                area=candidate.get("area"),
                capacity=candidate["capacity"],
                price_per_night=(
                    candidate["price_per_night"]
                ),
                total_price=pricing["total"],
                currency=candidate.get(
                    "currency",
                    "INR",
                ),
                number_of_nights=pricing[
                    "number_of_nights"
                ],
                amenities=candidate.get(
                    "combined_amenities",
                    [],
                ),
                score=score,
                match_reasons=reasons,
                available=True,
            )
        )

    options.sort(
        key=lambda option: (
            -option.score,
            option.price_per_night,
        )
    )

    return options[:limit]