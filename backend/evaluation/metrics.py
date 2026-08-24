from typing import Any


def get_nested_value(
    data: dict[str, Any],
    path: str,
) -> Any:
    """
    Retrieve a nested value using a dotted path.

    Example:
        get_nested_value(
            state,
            "guests.adults",
        )
    """
    current: Any = data

    for part in path.split("."):
        if not isinstance(current, dict):
            return None

        current = current.get(part)

    return current


def normalize_text(value: str) -> str:
    return " ".join(
        value.casefold().split()
    )


def evaluate_state(
    state: dict[str, Any],
    expected_state: dict[str, Any],
) -> list[str]:
    failures: list[str] = []

    for path, expected_value in (
        expected_state.items()
    ):
        actual_value = get_nested_value(
            state,
            path,
        )

        if actual_value != expected_value:
            failures.append(
                f"State '{path}': expected "
                f"{expected_value!r}, got "
                f"{actual_value!r}"
            )

    return failures


def evaluate_contains_in_state(
    state: dict[str, Any],
    expectations: dict[str, Any],
) -> list[str]:
    failures: list[str] = []

    for path, expected_item in (
        expectations.items()
    ):
        actual_value = get_nested_value(
            state,
            path,
        )

        if not isinstance(actual_value, list):
            failures.append(
                f"State '{path}' is not a list."
            )
            continue

        normalized_items = [
            normalize_text(str(item))
            for item in actual_value
        ]

        if (
            normalize_text(str(expected_item))
            not in normalized_items
        ):
            failures.append(
                f"State '{path}' does not contain "
                f"{expected_item!r}."
            )

    return failures


def collect_tool_names(
    responses: list[dict[str, Any]],
) -> list[str]:
    tool_names: list[str] = []

    for response in responses:
        for trace in response.get(
            "tool_traces",
            [],
        ):
            tool_name = (
                trace.get("tool")
                or trace.get("tool_name")
            )

            if tool_name:
                tool_names.append(tool_name)

    return tool_names


def evaluate_tools(
    tool_names: list[str],
    expected: dict[str, Any],
) -> list[str]:
    failures: list[str] = []

    for required_tool in expected.get(
        "required_tools",
        [],
    ):
        if required_tool not in tool_names:
            failures.append(
                f"Required tool was not called: "
                f"{required_tool}"
            )

    any_tools = expected.get(
        "any_tools",
        [],
    )

    if (
        any_tools
        and not any(
            tool in tool_names
            for tool in any_tools
        )
    ):
        failures.append(
            "None of the expected tools were called: "
            + ", ".join(any_tools)
        )

    for forbidden_tool in expected.get(
        "forbidden_tools",
        [],
    ):
        if forbidden_tool in tool_names:
            failures.append(
                f"Forbidden tool was called: "
                f"{forbidden_tool}"
            )

    return failures


def evaluate_response_text(
    response_text: str,
    expected: dict[str, Any],
) -> list[str]:
    failures: list[str] = []

    normalized_response = normalize_text(
        response_text
    )

    expected_phrases = expected.get(
        "response_any_phrases",
        [],
    )

    if expected_phrases:
        phrase_found = any(
            normalize_text(phrase)
            in normalized_response
            for phrase in expected_phrases
        )

        if not phrase_found:
            failures.append(
                "Response did not contain any expected "
                "phrase."
            )

    for phrase in expected.get(
        "forbidden_response_phrases",
        [],
    ):
        if (
            normalize_text(phrase)
            in normalized_response
        ):
            failures.append(
                f"Response contained forbidden phrase: "
                f"{phrase!r}"
            )

    return failures