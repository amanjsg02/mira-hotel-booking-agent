from app.repositories.hotel_repository import hotel_repository
from app.services.extractor import extract_destination
from app.tools.hotel_tools import search_properties


def test_destinations_come_from_dataset():
    destinations = hotel_repository.get_supported_destinations()

    assert "Goa" in destinations
    assert "Jaipur" in destinations
    assert "Manali" in destinations
    assert "Mumbai" in destinations


def test_extract_goa():
    assert (
        extract_destination(
            "Need something in Goa next weekend"
        )
        == "Goa"
    )


def test_extract_jaipur():
    assert (
        extract_destination(
            "Find a stay in Jaipur next weekend"
        )
        == "Jaipur"
    )


def test_extract_location_alias():
    assert (
        extract_destination(
            "I want to stay near Pink City"
        )
        == "Jaipur"
    )


def test_extract_unknown_destination():
    assert (
        extract_destination(
            "Find something in Kolkata next weekend"
        )
        == "Kolkata"
    )


def test_search_jaipur():
    results = search_properties(
        destination="Jaipur",
        guest_count=4,
        budget_per_night=15000
    )

    assert len(results) == 1
    assert results[0]["room_id"] == "haveli-family-suite"


def test_search_manali_for_six_guests():
    results = search_properties(
        destination="Manali",
        guest_count=6,
        budget_per_night=15000
    )

    assert len(results) == 1
    assert results[0]["room_id"] == "snowcrest-family-cottage"


def test_unsupported_destination_returns_no_inventory():
    results = search_properties(
        destination="Kolkata",
        guest_count=2,
        budget_per_night=10000
    )

    assert results == []