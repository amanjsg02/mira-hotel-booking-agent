# Engineering Note — Mera Hotel Booking AI Agent

## Overview

Mera is a conversational hotel booking agent built to understand guest requirements, maintain context across multiple messages, retrieve grounded hotel information, execute validated tools, calculate prices deterministically, and guide the guest toward a temporary booking hold.

The system uses a React frontend, FastAPI backend, Google Gemini for language understanding and tool selection, SQLite for persistent conversation memory, and a fictional JSON dataset for hotel inventory.

## Architecture

The application is divided into five main layers:

1. **React frontend** — displays the guest conversation, current booking state, recommendations, previous sessions, tool calls, tool results, next action, and errors.
2. **FastAPI API layer** — accepts chat requests, restores the session, invokes the orchestrator, stores messages, and returns a structured response.
3. **Agent orchestrator** — coordinates Gemini, conversation-state updates, tool selection, tool execution, and response generation.
4. **Deterministic tool layer** — performs hotel search, availability validation, recommendation ranking, room-detail retrieval, policy lookup, price calculation, and booking-hold creation.
5. **Persistence and data layer** — uses SQLite for sessions and `hotels.json` for grounded property inventory.

The high-level flow is:

```text
Guest message
→ load existing session
→ understand intent
→ update structured state
→ identify missing information
→ ask a question or execute a tool
→ validate tool result
→ generate grounded response
→ persist messages, state, and traces
```

## Model Choice

Google Gemini is used for natural-language understanding, contextual interpretation, structured state updates, tool selection, and guest-facing response generation.

The model is accessed through the `google-genai` SDK and configured using environment variables. The exact model name is not hard-coded into business logic, allowing it to be changed without modifying the application.

Gemini is not treated as the source of hotel facts or prices. Its responsibility is limited to understanding the conversation and deciding which controlled backend operation should happen next.

## State Management

Each conversation has a Pydantic-based structured state containing destination, dates, adults, children, budget, required amenities, preferred amenities, special requirements, recommendations, selected property, selected room, add-ons, and active hold information.

State updates are merged safely:

* Missing or `null` fields preserve existing values.
* Adults and children remain separate.
* Check-out must be after check-in.
* Changes to destination, dates, guests, budget, or amenities invalidate previous recommendations.
* Old property and room selections are cleared when they may no longer be valid.
* The complete state is validated before it is saved.

SQLite makes this state persistent across backend restarts and also stores conversation messages, tool traces, and booking holds.

## Tool Calling

Mera uses a controlled tool registry rather than allowing the model to perform arbitrary operations.

Implemented tools cover:

* Booking-state updates
* Supported-destination retrieval
* Property search
* Availability checking
* Ranked recommendations
* Room-detail retrieval
* Deterministic price calculation
* Policy lookup
* Temporary booking-hold creation

Before execution, tool arguments are validated against the current conversation state. Tool execution returns structured success or error results, which are stored as traces and displayed in the frontend.

The orchestrator also limits the maximum number of model/tool iterations to prevent an infinite execution loop.

## Recommendation and Pricing

Recommendation logic applies hard constraints before ranking:

* Destination
* Date validity
* Availability
* Guest capacity
* Required amenities
* Budget, when provided

Valid rooms are ranked using preference matches, budget fit, capacity fit, and included benefits.

Pricing is calculated by backend logic:

```text
Room subtotal = nightly price × number of nights
Final total   = room subtotal + selected add-ons
```

This avoids relying on the LLM for arithmetic and makes pricing behavior deterministic and testable.

## Hallucination Prevention

Mera prevents unsupported hotel claims through the following controls:

* Properties, rooms, prices, amenities, policies, capacity, and availability come only from `hotels.json`.
* Tool results are treated as the source of truth.
* Unsupported destinations do not receive invented hotel recommendations.
* Missing information is explicitly described as unavailable or unspecified.
* Capacity and availability are validated before recommendation or hold creation.
* Required amenities are enforced as hard constraints.
* Pricing is handled by deterministic application logic.
* Pydantic validates structured state and API responses.
* Tool traces make operational behavior inspectable without exposing private chain of thought.

## Testing and Evaluation

The project separates deterministic tests from live-AI tests.

Non-AI tests validate state updates, date parsing, hotel retrieval, capacity, recommendations, pricing, persistence, API behavior, session deletion, and booking holds without calling Gemini.

Live-AI tests verify that Gemini is enabled and can update booking state through the real agent flow.

A conversational evaluation suite covers 12 scenarios, including context changes, adult and child separation, relative updates, required and preferred amenities, unsupported destinations, unknown information, capacity conflicts, cheaper-option recovery, and invalid date order.

GitHub Actions automatically runs the deterministic test suite on pushes and pull requests.

## Trade-offs and Limitations

The hotel inventory is intentionally small and fictional, which keeps the assignment reliable and easy to evaluate but does not represent real-time hotel supply.

SQLite provides simple persistent storage but is not suitable for high-concurrency, multi-instance production deployment. Booking holds are demonstration records and do not connect to payments or an actual reservation system.

Live-agent behavior also depends on Gemini availability, quota, model access, and network conditions. For this reason, external AI tests are kept separate from deterministic CI tests.

## Improvements

The next production improvements would be:

* Replace SQLite with PostgreSQL.
* Use Redis for distributed state and booking-hold expiration.
* Integrate a real hotel inventory or property-management API.
* Add authentication and guest profiles.
* Add payment and booking-confirmation workflows.
* Stream responses to the frontend.
* Add structured logging, tracing, metrics, and alerting.
* Add multilingual support.
* Add prompt and model versioning with automated evaluation comparisons.

The current design intentionally prioritizes a smaller, understandable system that runs reliably and demonstrates the complete guest-message-to-booking workflow.
