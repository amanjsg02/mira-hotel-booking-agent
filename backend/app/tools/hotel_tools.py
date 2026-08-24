from datetime import date, timedelta
from typing import Any

from app.repositories.hotel_repository import hotel_repository

from datetime import (
    date,
    datetime,
    timedelta,
    timezone,
)
from uuid import uuid4

from app.models import BookingHold
from app.repositories.hold_repository import (
    hold_repository,
)


def date_range(
    check_in: date,
    check_out: date
) -> list[date]:
    """
    Return all occupied dates for a booking.

    Example:
    Check-in:  10 September
    Check-out: 13 September

    Occupied nights:
    10, 11 and 12 September
    """
    if check_out <= check_in:
        raise ValueError("Check-out must be after check-in.")

    number_of_nights = (check_out - check_in).days

    return [
        check_in + timedelta(days=offset)
        for offset in range(number_of_nights)
    ]


def room_is_available(
    room: dict[str, Any],
    check_in: date,
    check_out: date
) -> bool:
    """
    Check whether any requested stay date conflicts with
    the room's unavailable dates.
    """
    requested_dates = {
        requested_date.isoformat()
        for requested_date in date_range(check_in, check_out)
    }

    unavailable_dates = set(
        room.get("unavailable_dates", [])
    )

    return requested_dates.isdisjoint(unavailable_dates)


def supports_required_amenities(
    hotel: dict[str, Any],
    room: dict[str, Any],
    required_amenities: list[str]
) -> bool:
    """
    Verify that the property or room satisfies all requested
    amenities.

    Some requirements can be satisfied through policies or add-ons:
    - pets_allowed may be represented by a hotel policy.
    - breakfast may be included in the room or available as an add-on.
    """
    available_amenities = set(
        hotel.get("amenities", [])
        + room.get("amenities", [])
    )

    remaining_requirements = set(required_amenities)

    if (
        "pets_allowed" in remaining_requirements
        and hotel.get("policies", {}).get("pets_allowed") is True
    ):
        remaining_requirements.remove("pets_allowed")

    if "breakfast" in remaining_requirements:
        breakfast_included = (
            "breakfast_included" in available_amenities
        )

        breakfast_add_on_available = any(
            add_on.get("name", "").casefold() == "breakfast"
            or "breakfast" in add_on.get("id", "").casefold()
            for add_on in hotel.get("add_ons", [])
        )

        if breakfast_included or breakfast_add_on_available:
            remaining_requirements.remove("breakfast")

    return remaining_requirements.issubset(
        available_amenities
    )


def get_supported_destinations() -> list[str]:
    """
    Return all cities for which the local dataset contains
    at least one hotel.

    The result is generated from hotels.json, so a new destination
    can be supported by adding a new property to the dataset without
    changing this Python file.
    """
    return hotel_repository.get_supported_destinations()


def search_properties(
    destination: str,
    guest_count: int,
    budget_per_night: int | None = None,
    required_amenities: list[str] | None = None
) -> list[dict[str, Any]]:
    """
    Search all hotel rooms that satisfy:
    - Destination
    - Guest capacity
    - Optional nightly budget
    - Optional amenity requirements

    Availability is checked separately through check_availability().
    """
    if guest_count <= 0:
        raise ValueError(
            "Guest count must be greater than zero."
        )

    required_amenities = required_amenities or []

    hotels = hotel_repository.find_by_destination(
        destination
    )

    results: list[dict[str, Any]] = []

    for hotel in hotels:
        property_amenities = hotel.get("amenities", [])

        for room in hotel.get("rooms", []):
            if room.get("capacity", 0) < guest_count:
                continue

            room_price = room.get("price_per_night")

            if room_price is None:
                # A room with an unknown price should not be
                # presented as a priced recommendation.
                continue

            if (
                budget_per_night is not None
                and room_price > budget_per_night
            ):
                continue

            if not supports_required_amenities(
                hotel=hotel,
                room=room,
                required_amenities=required_amenities
            ):
                continue

            combined_amenities = sorted(
                set(
                    property_amenities
                    + room.get("amenities", [])
                )
            )

            results.append({
                "property_id": hotel["id"],
                "property_name": hotel["name"],
                "city": hotel["location"]["city"],
                "state": hotel["location"].get("state"),
                "country": hotel["location"].get("country"),
                "area": hotel["location"].get("area"),
                "room_id": room["id"],
                "room_name": room["name"],
                "capacity": room["capacity"],
                "price_per_night": room_price,
                "currency": hotel.get("currency", "INR"),
                "property_amenities": property_amenities,
                "room_amenities": room.get("amenities", []),
                "combined_amenities": combined_amenities
            })

    return sorted(
        results,
        key=lambda result: result["price_per_night"]
    )


def check_availability(
    room_id: str,
    check_in: date,
    check_out: date
) -> dict[str, Any]:
    """
    Check whether a particular room type is available for the
    requested dates.
    """
    room_record = hotel_repository.get_room(room_id)

    if room_record is None:
        raise ValueError(
            f"Unknown room ID: {room_id}"
        )

    hotel, room = room_record

    available = room_is_available(
        room=room,
        check_in=check_in,
        check_out=check_out
    )

    return {
        "property_id": hotel["id"],
        "property_name": hotel["name"],
        "room_id": room["id"],
        "room_name": room["name"],
        "check_in": check_in.isoformat(),
        "check_out": check_out.isoformat(),
        "available": available,
        "available_quantity": (
            room.get("quantity", 0)
            if available
            else 0
        )
    }


def get_room_details(
    room_id: str
) -> dict[str, Any]:
    """
    Return grounded property, room, policy and add-on information
    for a room ID.
    """
    room_record = hotel_repository.get_room(room_id)

    if room_record is None:
        raise ValueError(
            f"Unknown room ID: {room_id}"
        )

    hotel, room = room_record

    return {
        "property_id": hotel["id"],
        "property_name": hotel["name"],
        "currency": hotel.get("currency", "INR"),
        "location": hotel["location"],
        "property_amenities": hotel.get("amenities", []),
        "room": room,
        "policies": hotel.get("policies", {}),
        "add_ons": hotel.get("add_ons", [])
    }


def get_policy(
    property_id: str,
    policy_name: str | None = None
) -> dict[str, Any]:
    """
    Return all policies or a specific policy for a property.

    If a requested policy is not present, known=False is returned.
    This prevents the application from inventing unknown policies.
    """
    hotel = hotel_repository.get_property(property_id)

    if hotel is None:
        raise ValueError(
            f"Unknown property ID: {property_id}"
        )

    policies = hotel.get("policies", {})

    if policy_name is None:
        return {
            "property_id": property_id,
            "property_name": hotel["name"],
            "known": bool(policies),
            "policies": policies
        }

    normalized_policy_name = (
        policy_name.strip().lower().replace(" ", "_")
    )

    if normalized_policy_name not in policies:
        return {
            "property_id": property_id,
            "property_name": hotel["name"],
            "policy": normalized_policy_name,
            "known": False,
            "value": None,
            "message": (
                f"The dataset does not specify the "
                f"{normalized_policy_name.replace('_', ' ')} "
                f"policy for {hotel['name']}."
            )
        }

    return {
        "property_id": property_id,
        "property_name": hotel["name"],
        "policy": normalized_policy_name,
        "known": True,
        "value": policies[normalized_policy_name]
    }


def calculate_price(
    room_id: str,
    check_in: date,
    check_out: date,
    guest_count: int,
    selected_add_ons: list[str] | None = None
) -> dict[str, Any]:
    """
    Calculate the complete booking price using deterministic
    application logic.

    The model should never calculate or invent the final price.
    """
    if guest_count <= 0:
        raise ValueError(
            "Guest count must be greater than zero."
        )

    selected_add_ons = selected_add_ons or []

    details = get_room_details(room_id)
    room = details["room"]

    if guest_count > room["capacity"]:
        raise ValueError(
            f"{room['name']} supports at most "
            f"{room['capacity']} guests, but "
            f"{guest_count} guests were requested."
        )

    number_of_nights = (
        check_out - check_in
    ).days

    if number_of_nights <= 0:
        raise ValueError(
            "Stay must be at least one night."
        )

    price_per_night = room.get("price_per_night")

    if price_per_night is None:
        raise ValueError(
            f"Price information is unavailable for "
            f"{room['name']}."
        )

    room_subtotal = (
        price_per_night * number_of_nights
    )

    available_add_ons = {
        add_on["id"]: add_on
        for add_on in details.get("add_ons", [])
    }

    add_on_total = 0
    add_on_breakdown: list[dict[str, Any]] = []

    for add_on_id in selected_add_ons:
        add_on = available_add_ons.get(add_on_id)

        if add_on is None:
            raise ValueError(
                f"Add-on '{add_on_id}' is not available "
                f"for {details['property_name']}."
            )

        add_on_price = add_on.get("price")

        if add_on_price is None:
            raise ValueError(
                f"Price information is unavailable for "
                f"add-on '{add_on['name']}'."
            )

        pricing_type = add_on.get("pricing_type")

        if pricing_type == "per_booking":
            amount = add_on_price

        elif pricing_type == "per_night":
            amount = (
                add_on_price * number_of_nights
            )

        elif pricing_type == "per_guest":
            amount = (
                add_on_price * guest_count
            )

        elif pricing_type == "per_guest_per_night":
            amount = (
                add_on_price
                * guest_count
                * number_of_nights
            )

        else:
            raise ValueError(
                f"Unsupported pricing type "
                f"'{pricing_type}' for add-on "
                f"'{add_on['name']}'."
            )

        add_on_total += amount

        add_on_breakdown.append({
            "id": add_on["id"],
            "name": add_on["name"],
            "unit_price": add_on_price,
            "pricing_type": pricing_type,
            "amount": amount
        })

    total = room_subtotal + add_on_total

    return {
        "property_id": details["property_id"],
        "property_name": details["property_name"],
        "room_id": room["id"],
        "room_name": room["name"],
        "currency": details["currency"],
        "check_in": check_in.isoformat(),
        "check_out": check_out.isoformat(),
        "number_of_nights": number_of_nights,
        "guest_count": guest_count,
        "price_per_night": price_per_night,
        "room_subtotal": room_subtotal,
        "selected_add_ons": add_on_breakdown,
        "add_on_total": add_on_total,
        "total": total
    }
def create_booking_hold(
    session_id: str,
    room_id: str,
    check_in: date,
    check_out: date,
    guest_count: int,
    selected_add_ons: list[str] | None = None,
) -> dict[str, Any]:
    """
    Revalidate and create a temporary 15-minute booking hold.

    The price is always recalculated by application logic.
    """
    selected_add_ons = selected_add_ons or []

    details = get_room_details(room_id)
    room = details["room"]

    if guest_count > room["capacity"]:
        raise ValueError(
            f"{room['name']} supports at most "
            f"{room['capacity']} guests."
        )

    availability = check_availability(
        room_id=room_id,
        check_in=check_in,
        check_out=check_out,
    )

    if not availability["available"]:
        raise ValueError(
            "The selected room is no longer available."
        )

    pricing = calculate_price(
        room_id=room_id,
        check_in=check_in,
        check_out=check_out,
        guest_count=guest_count,
        selected_add_ons=selected_add_ons,
    )

    created_at = datetime.now(timezone.utc)
    expires_at = created_at + timedelta(
        minutes=15
    )

    hold = BookingHold(
        hold_id=(
            f"HOLD-{uuid4().hex[:10].upper()}"
        ),
        session_id=session_id,
        property_id=details["property_id"],
        property_name=details["property_name"],
        room_id=room["id"],
        room_name=room["name"],
        check_in=check_in,
        check_out=check_out,
        guest_count=guest_count,
        selected_add_ons=selected_add_ons,
        currency=details["currency"],
        total=pricing["total"],
        status="held",
        created_at=created_at,
        expires_at=expires_at,
    )

    saved_hold = hold_repository.save(hold)

    return saved_hold.model_dump(
        mode="json"
    )


def get_booking_hold(
    hold_id: str,
) -> dict[str, Any]:
    """
    Retrieve a temporary hold and refresh its status.
    """
    hold = hold_repository.get(hold_id)

    if hold is None:
        raise ValueError(
            f"Unknown hold ID: {hold_id}"
        )

    return hold.model_dump(mode="json")


def cancel_booking_hold(
    hold_id: str,
) -> dict[str, Any]:
    """
    Cancel an existing temporary hold.
    """
    hold = hold_repository.cancel(hold_id)

    if hold is None:
        raise ValueError(
            f"Unknown hold ID: {hold_id}"
        )

    return hold.model_dump(mode="json")