from datetime import date

import pytest

from app.models import ConversationState
from app.services.state_merger import (
    merge_state_update,
)


@pytest.mark.unit
def test_budget_update_preserves_context():
    current = ConversationState()

    current.destination = "Goa"
    current.check_in = date(
        2026,
        9,
        5,
    )
    current.check_out = date(
        2026,
        9,
        8,
    )
    current.guests.adults = 2
    current.guests.children = 0
    current.budget_per_night = 15000

    updated = merge_state_update(
        current=current,
        update={
            "budget_per_night": 20000,
        },
    )

    assert updated.destination == "Goa"
    assert updated.check_in == date(
        2026,
        9,
        5,
    )
    assert updated.check_out == date(
        2026,
        9,
        8,
    )
    assert updated.guests.adults == 2
    assert updated.guests.children == 0
    assert updated.budget_per_night == 20000


@pytest.mark.unit
def test_adults_and_children_remain_separate():
    current = ConversationState()

    updated = merge_state_update(
        current=current,
        update={
            "adults": 3,
            "children": 2,
        },
    )

    assert updated.guests.adults == 3
    assert updated.guests.children == 2

    total_guests = (
        updated.guests.adults
        + updated.guests.children
    )

    assert total_guests == 5


@pytest.mark.unit
def test_update_only_children():
    current = ConversationState()

    current.guests.adults = 3
    current.guests.children = 2

    updated = merge_state_update(
        current=current,
        update={
            "children": 1,
        },
    )

    assert updated.guests.adults == 3
    assert updated.guests.children == 1


@pytest.mark.unit
def test_date_change_clears_recommendations():
    current = ConversationState()

    current.destination = "Goa"
    current.check_in = date(
        2026,
        9,
        5,
    )
    current.check_out = date(
        2026,
        9,
        8,
    )
    current.selected_property_id = (
        "test-property"
    )
    current.selected_room_id = "test-room"

    updated = merge_state_update(
        current=current,
        update={
            "check_out": "2026-09-09",
        },
    )

    assert updated.check_out == date(
        2026,
        9,
        9,
    )
    assert updated.selected_property_id is None
    assert updated.selected_room_id is None
    assert updated.last_search_results == []


@pytest.mark.unit
def test_invalid_date_order_is_rejected():
    current = ConversationState()

    current.check_in = date(
        2026,
        9,
        10,
    )

    with pytest.raises(
        ValueError,
        match="Check-out must be after check-in",
    ):
        merge_state_update(
            current=current,
            update={
                "check_out": "2026-09-08",
            },
        )


@pytest.mark.unit
def test_null_values_preserve_state():
    current = ConversationState()

    current.destination = "Jaipur"
    current.budget_per_night = 15000
    current.guests.adults = 4

    updated = merge_state_update(
        current=current,
        update={
            "destination": None,
            "budget_per_night": None,
            "adults": None,
        },
    )

    assert updated.destination == "Jaipur"
    assert updated.budget_per_night == 15000
    assert updated.guests.adults == 4


@pytest.mark.unit
def test_required_amenity_clears_old_results():
    current = ConversationState()

    current.last_search_results = []
    current.selected_property_id = "property-1"
    current.selected_room_id = "room-1"

    updated = merge_state_update(
        current=current,
        update={
            "required_amenities": [
                "private_pool",
            ],
        },
    )

    assert updated.required_amenities == [
        "private_pool",
    ]
    assert updated.selected_property_id is None
    assert updated.selected_room_id is None


@pytest.mark.unit
def test_preferred_amenity_does_not_become_required():
    current = ConversationState()

    updated = merge_state_update(
        current=current,
        update={
            "preferred_amenities": [
                "breakfast",
            ],
        },
    )

    assert updated.preferred_amenities == [
        "breakfast",
    ]
    assert updated.required_amenities == []