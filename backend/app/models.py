from datetime import date, datetime, timezone
from typing import Any, Literal
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator


class GuestComposition(BaseModel):
    """
    Stores the number and type of guests.

    `adults=None` means the guest count has not yet been provided.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    adults: int | None = Field(
        default=None,
        ge=1,
        le=20,
        description="Number of adult guests",
    )

    children: int = Field(
        default=0,
        ge=0,
        le=20,
        description="Number of child guests",
    )

    @property
    def total(self) -> int | None:
        """
        Return the total number of guests.

        If the adult count is unknown, the total is also unknown.
        """
        if self.adults is None:
            return None

        return self.adults + self.children


from datetime import date, datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class RoomOption(BaseModel):
    """
    One available and ranked room recommendation.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    property_id: str
    property_name: str
    room_id: str
    room_name: str

    city: str
    area: str | None = None

    capacity: int = Field(ge=1)
    price_per_night: int = Field(ge=0)
    total_price: int = Field(ge=0)
    currency: str = "INR"
    number_of_nights: int = Field(ge=1)

    amenities: list[str] = Field(
        default_factory=list
    )

    score: float = 0
    match_reasons: list[str] = Field(
        default_factory=list
    )

    available: bool = True


class AddOnRecommendation(BaseModel):
    """
    One contextually relevant add-on.
    """

    id: str
    name: str
    price: int = Field(ge=0)
    pricing_type: str
    reason: str


class BookingHold(BaseModel):
    """
    Temporary booking hold returned to the guest.
    """

    hold_id: str
    session_id: str

    property_id: str
    property_name: str
    room_id: str
    room_name: str

    check_in: date
    check_out: date
    guest_count: int = Field(ge=1)

    selected_add_ons: list[str] = Field(
        default_factory=list
    )

    currency: str = "INR"
    total: int = Field(ge=0)

    status: Literal[
        "held",
        "expired",
        "cancelled",
    ] = "held"

    created_at: datetime
    expires_at: datetime


class ConversationState(BaseModel):
    """
    Structured information remembered during a booking
    conversation.

    New values extracted from a message are merged into the
    existing state rather than replacing the complete state.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    destination: str | None = Field(
        default=None,
        max_length=100,
        description="Requested city or destination",
    )

    check_in: date | None = Field(
        default=None,
        description="Requested check-in date",
    )

    check_out: date | None = Field(
        default=None,
        description="Requested check-out date",
    )

    guests: GuestComposition = Field(
        default_factory=GuestComposition,
    )

    budget_per_night: int | None = Field(
        default=None,
        ge=0,
        description="Maximum nightly room budget",
    )

    required_amenities: list[str] = Field(
        default_factory=list
    )

    preferred_amenities: list[str] = Field(
        default_factory=list,
        description="Requested room or property amenities",
    )

    special_requirements: list[str] = Field(
        default_factory=list,
        description="Other guest requirements",
    )

    selected_property_id: str | None = Field(
        default=None,
        description="Currently recommended or selected property",
    )

    selected_room_id: str | None = Field(
        default=None,
        description="Currently recommended or selected room",
    )

    last_search_results: list[RoomOption] = Field(
        default_factory=list
    )

    current_option_index: int | None = None

    selected_add_ons: list[str] = Field(
        default_factory=list
    )

    suggested_add_ons: list[
        AddOnRecommendation
    ] = Field(default_factory=list) 

    last_agent_action: str | None = None

    pending_confirmation: str | None = None

    active_hold_id: str | None = None

    @field_validator(
    "required_amenities",
    "preferred_amenities",
    "special_requirements",
    "selected_add_ons",
    )
    @classmethod
    def normalize_string_lists(
    cls,
    values: list[str],
) -> list[str]:
     normalized_values = []
     seen = set()

     for value in values:
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


class ChatRequest(BaseModel):
    """
    Request sent from React to FastAPI.

    request_id prevents duplicate processing.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    request_id: str = Field(
        min_length=1,
        max_length=128,
    )

    session_id: str = Field(
        min_length=1,
        max_length=128,
    )

    message: str = Field(
        min_length=1,
        max_length=2000,
    )

    @field_validator(
        "request_id",
        "session_id",
        "message",
    )
    @classmethod
    def remove_whitespace(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Value cannot be empty."
            )

        return normalized

class ToolTrace(BaseModel):
    """
    Auditable record of a tool execution.

    This records structured application activity:
    - Tool selected
    - Arguments supplied
    - Result returned
    - Execution status

    It does not contain private chain-of-thought.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    tool: str = Field(
        min_length=1,
        description="Registered tool name",
    )

    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments supplied to the tool",
    )

    result: Any = Field(
        default=None,
        description="Structured tool result or error",
    )

    status: Literal["success", "error"] = Field(
        default="success",
        description="Whether tool execution succeeded",
    )


class ChatResponse(BaseModel):
    """
    Response returned by POST /api/chat.

    Phase 4 adds:
    - request_id for duplicate-request protection
    - agent_mode to show whether Gemini or fallback responded
    - model_name for debugging and UI visibility
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    request_id: str | None = Field(
        default=None,
        description=(
            "Unique frontend request identifier used for "
            "idempotency"
        ),
    )

    session_id: str = Field(
        min_length=1,
        description="Conversation session identifier",
    )

    response: str = Field(
        min_length=1,
        description="Natural-language response for the guest",
    )

    state: ConversationState

    action: str = Field(
        min_length=1,
        description="Structured action performed by the agent",
        examples=["recommend_room"],
    )

    next_action: str = Field(
        min_length=1,
        description="Expected next conversational action",
        examples=["offer_details_or_booking_hold"],
    )

    tool_traces: list[ToolTrace] = Field(
        default_factory=list,
        description=(
            "Structured tool executions performed during "
            "this turn"
        ),
    )

    agent_mode: str = Field(
        default="unknown",
        description=(
            "Execution mode used for the response, such as "
            "'gemini', 'phase1_fallback', or "
            "'provider_error'"
        ),
        examples=["gemini"],
    )

    model_name: str | None = Field(
        default=None,
        description=(
            "Name of the LLM used to generate the response"
        ),
        examples=["gemini-3.6-flash"],
    )

class ConversationMessage(BaseModel):
    """
    One persisted guest or agent message.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    message_id: str = Field(
        default_factory=lambda: (
            f"msg-{uuid4().hex}"
        )
    )

    session_id: str

    role: Literal[
        "guest",
        "agent",
    ]

    content: str = Field(
        min_length=1,
        max_length=10000,
    )

    created_at: datetime = Field(
        default_factory=lambda: (
            datetime.now(timezone.utc)
        )
    )