import json
from pathlib import Path
from typing import Any


DATA_FILE = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "hotels.json"
)


class HotelRepository:
    def __init__(self, data_file: Path = DATA_FILE):
        self.data_file = data_file
        self._hotels = self._load()

    def _load(self) -> list[dict[str, Any]]:
        with self.data_file.open("r", encoding="utf-8") as file:
            return json.load(file)

    def get_all(self) -> list[dict[str, Any]]:
        return self._hotels

    def get_supported_destinations(self) -> list[str]:
        destinations = {
            hotel["location"]["city"]
            for hotel in self._hotels
        }
        return sorted(destinations)

    def get_location_terms(self) -> dict[str, str]:
        """
        Returns:
        {
            "goa": "Goa",
            "north goa": "Goa",
            "candolim": "Goa",
            "pink city": "Jaipur",
            ...
        }
        """
        locations: dict[str, str] = {}

        for hotel in self._hotels:
            location = hotel["location"]
            canonical_city = location["city"]

            terms = [
                location.get("city"),
                location.get("state"),
                location.get("area"),
                *location.get("aliases", [])
            ]

            for term in terms:
                if term:
                    locations[term.casefold()] = canonical_city

        return locations

    def find_by_destination(
        self,
        destination: str
    ) -> list[dict[str, Any]]:
        normalized = destination.casefold()

        return [
            hotel
            for hotel in self._hotels
            if hotel["location"]["city"].casefold() == normalized
        ]

    def get_property(
        self,
        property_id: str
    ) -> dict[str, Any] | None:
        return next(
            (
                hotel
                for hotel in self._hotels
                if hotel["id"] == property_id
            ),
            None
        )

    def get_room(
        self,
        room_id: str
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        for hotel in self._hotels:
            for room in hotel["rooms"]:
                if room["id"] == room_id:
                    return hotel, room

        return None


hotel_repository = HotelRepository()