import re
from datetime import timedelta

from app.models import ConversationState
from app.repositories.hotel_repository import hotel_repository
from app.services.date_parser import extract_relative_dates


AMENITY_ALIASES = {
    "private pool": "private_pool",
    "pool villa": "private_pool",
    "swimming pool": "swimming_pool",
    "pool": "swimming_pool",
    "near the beach": "beach_access",
    "beach access": "beach_access",
    "breakfast": "breakfast",
    "parking": "parking",
    "pet friendly": "pets_allowed",
    "pets allowed": "pets_allowed",
    "wifi": "wifi",
    "mountain view": "mountain_view",
    "gym": "gym",
    "spa": "spa",
    "heater": "heater"
}


def extract_number_before(
    message: str,
    words: list[str]
) -> int | None:
    word_group = "|".join(re.escape(word) for word in words)

    match = re.search(
        rf"\b(\d+)\s*(?:{word_group})\b",
        message,
        flags=re.IGNORECASE
    )

    return int(match.group(1)) if match else None


def extract_destination(message: str) -> str | None:
    normalized = message.casefold()
    location_terms = hotel_repository.get_location_terms()

    # Longer terms should be checked first.
    # For example, "north goa" should be checked before "goa".
    sorted_terms = sorted(
        location_terms.keys(),
        key=len,
        reverse=True
    )

    for term in sorted_terms:
        pattern = rf"\b{re.escape(term)}\b"

        if re.search(pattern, normalized):
            return location_terms[term]

    # Generic patterns capture destinations not present in inventory.
    patterns = [
        r"\b(?:in|at|near|around|for)\s+"
        r"([a-zA-Z][a-zA-Z\s'-]{1,40}?)"
        r"(?=\s+(?:this|next|from|on|under|for|with)\b|[,.!?]|$)",

        r"\b(?:visit|travel(?:ling)? to|going to|stay in)\s+"
        r"([a-zA-Z][a-zA-Z\s'-]{1,40}?)"
        r"(?=\s+(?:this|next|from|on|under|for|with)\b|[,.!?]|$)"
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            message,
            flags=re.IGNORECASE
        )

        if match:
            destination = match.group(1).strip()

            excluded_values = {
                "something",
                "a hotel",
                "a room",
                "my family"
            }

            if destination.casefold() not in excluded_values:
                return destination.title()

    return None


def update_state_from_message(
    current: ConversationState,
    message: str
) -> ConversationState:
    state = current.model_copy(deep=True)
    normalized = message.lower().strip()

    destination = extract_destination(message)

    if destination:
        state.destination = destination

        # New destination invalidates old room selections.
        state.selected_property_id = None
        state.selected_room_id = None

    adults = extract_number_before(
        normalized,
        [
            "adult",
            "adults",
            "people",
            "persons",
            "guests"
        ]
    )

    children = extract_number_before(
        normalized,
        ["kid", "kids", "child", "children"]
    )

    friends_match = re.search(
        r"my\s+(\d+)\s+friends?\s+and\s+me",
        normalized
    )

    if friends_match:
        adults = int(friends_match.group(1)) + 1

    if "my wife" in normalized or "my husband" in normalized:
        if adults is None:
            adults = 2

    change_match = re.search(
        r"(?:make that|change (?:it )?to)\s+(\d+)\s*"
        r"(?:people|guests|persons)",
        normalized
    )

    if change_match:
        adults = int(change_match.group(1))

        # In this simple Phase 1 model, "4 people" means
        # four adults unless the guest separately specifies children.
        children = 0

    if adults is not None:
        state.guests.adults = adults

    if children is not None:
        state.guests.children = children

    budget_match = re.search(
        r"(?:under|below|up to|max(?:imum)?|budget(?: of| is)?)\s*"
        r"(?:₹|rs\.?|inr)?\s*([\d,.]+)\s*(k)?",
        normalized
    )

    if budget_match:
        budget = float(
            budget_match.group(1).replace(",", "")
        )

        if budget_match.group(2):
            budget *= 1000

        state.budget_per_night = int(budget)

    for phrase, amenity in AMENITY_ALIASES.items():
        if phrase in normalized:
            if amenity not in state.preferred_amenities:
                state.preferred_amenities.append(amenity)

    check_in, check_out = extract_relative_dates(normalized)

    if check_in:
        state.check_in = check_in

    if check_out:
        state.check_out = check_out

    if (
        state.check_out
        and re.search(r"(?:one|1)\s+more\s+night", normalized)
    ):
        state.check_out += timedelta(days=1)

    return state


def find_missing_required_fields(
    state: ConversationState
) -> list[str]:
    missing = []

    if not state.destination:
        missing.append("destination")

    if not state.check_in or not state.check_out:
        missing.append("dates")

    if state.guests.total is None:
        missing.append("guests")

    return missing