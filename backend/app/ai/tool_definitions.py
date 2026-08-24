AI_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "name": "update_booking_state",
        "description": (
            "Update booking information extracted from the "
            "guest's latest message. Pass null for fields that "
            "were not mentioned and should remain unchanged."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "destination": {
                    "type": ["string", "null"],
                    "description": (
                        "Requested destination or city."
                    ),
                },
                "check_in": {
                    "type": ["string", "null"],
                    "description": (
                        "Check-in date in YYYY-MM-DD format."
                    ),
                },
                "check_out": {
                    "type": ["string", "null"],
                    "description": (
                        "Check-out date in YYYY-MM-DD format."
                    ),
                },
                "adults": {
                    "type": ["integer", "null"],
                    "description": "Number of adults.",
                },
                "children": {
                    "type": ["integer", "null"],
                    "description": "Number of children.",
                },
                "budget_per_night": {
                    "type": ["integer", "null"],
                    "description": (
                        "Maximum nightly budget in INR."
                    ),
                },
                "preferred_amenities": {
                    "type": ["array", "null"],
                    "items": {
                        "type": "string",
                    },
                    "description": (
                        "Amenities explicitly requested by "
                        "the guest."
                    ),
                },
                "special_requirements": {
                    "type": ["array", "null"],
                    "items": {
                        "type": "string",
                    },
                    "description": (
                        "Other requirements mentioned by "
                        "the guest."
                    ),
                },
            },
            "required": [
                "destination",
                "check_in",
                "check_out",
                "adults",
                "children",
                "budget_per_night",
                "preferred_amenities",
                "special_requirements",
            ],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_supported_destinations",
        "description": (
            "Return destinations that have hotel inventory."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "search_properties",
        "description": (
            "Search rooms matching destination, capacity, "
            "nightly budget and requested amenities. This "
            "does not confirm availability."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "destination": {
                    "type": "string",
                },
                "guest_count": {
                    "type": "integer",
                    "minimum": 1,
                },
                "budget_per_night": {
                    "type": ["integer", "null"],
                },
                "required_amenities": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
            },
            "required": [
                "destination",
                "guest_count",
                "budget_per_night",
                "required_amenities",
            ],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "check_availability",
        "description": (
            "Check whether one room type is available for "
            "the requested stay dates."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "room_id": {
                    "type": "string",
                },
                "check_in": {
                    "type": "string",
                    "description": "YYYY-MM-DD",
                },
                "check_out": {
                    "type": "string",
                    "description": "YYYY-MM-DD",
                },
            },
            "required": [
                "room_id",
                "check_in",
                "check_out",
            ],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_room_details",
        "description": (
            "Get factual room, property, amenity, policy and "
            "add-on information for a room."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "room_id": {
                    "type": "string",
                },
            },
            "required": ["room_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_policy",
        "description": (
            "Get all policies or one named policy for a "
            "selected property."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "property_id": {
                    "type": "string",
                },
                "policy_name": {
                    "type": ["string", "null"],
                },
            },
            "required": [
                "property_id",
                "policy_name",
            ],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "calculate_price",
        "description": (
            "Calculate the deterministic total price for a "
            "room, stay and selected add-ons."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "room_id": {
                    "type": "string",
                },
                "check_in": {
                    "type": "string",
                    "description": "YYYY-MM-DD",
                },
                "check_out": {
                    "type": "string",
                    "description": "YYYY-MM-DD",
                },
                "guest_count": {
                    "type": "integer",
                    "minimum": 1,
                },
                "selected_add_ons": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
            },
            "required": [
                "room_id",
                "check_in",
                "check_out",
                "guest_count",
                "selected_add_ons",
            ],
            "additionalProperties": False,
        },
    },
]