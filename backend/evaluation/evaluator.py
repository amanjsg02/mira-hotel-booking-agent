import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from evaluation.metrics import (
    collect_tool_names,
    evaluate_contains_in_state,
    evaluate_response_text,
    evaluate_state,
    evaluate_tools,
)


BASE_DIR = Path(__file__).resolve().parent

SCENARIOS_FILE = (
    BASE_DIR / "conversations.json"
)

REPORTS_DIR = BASE_DIR / "reports"

DEFAULT_API_URL = (
    "http://127.0.0.1:8000"
)


def load_scenarios() -> list[dict[str, Any]]:
    with SCENARIOS_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def run_scenario(
    client: httpx.Client,
    api_url: str,
    scenario: dict[str, Any],
) -> dict[str, Any]:
    session_id = (
        f"eval-{scenario['id']}-"
        f"{uuid4().hex}"
    )

    responses: list[dict[str, Any]] = []
    request_errors: list[str] = []

    for message in scenario["messages"]:
        request_id = (
            f"eval-request-{uuid4().hex}"
        )

        try:
            response = client.post(
                f"{api_url}/api/chat",
                json={
                    "request_id": request_id,
                    "session_id": session_id,
                    "message": message,
                },
            )

            response.raise_for_status()
            responses.append(response.json())
        except Exception as exc:
            request_errors.append(str(exc))
            break

    failures = list(request_errors)

    if responses:
        final_response = responses[-1]
        expected = scenario.get(
            "expected",
            {},
        )

        state = final_response.get(
            "state",
            {},
        )

        failures.extend(
            evaluate_state(
                state,
                expected.get("state", {}),
            )
        )

        failures.extend(
            evaluate_contains_in_state(
                state,
                expected.get(
                    "contains_in_state",
                    {},
                ),
            )
        )

        tool_names = collect_tool_names(
            responses
        )

        failures.extend(
            evaluate_tools(
                tool_names,
                expected,
            )
        )

        failures.extend(
            evaluate_response_text(
                final_response.get(
                    "response",
                    "",
                ),
                expected,
            )
        )
    else:
        final_response = {}
        tool_names = []
    all_tool_traces = []

    for response_item in responses:
        all_tool_traces.extend(
            response_item.get(
                "tool_traces",
                []
            )
        )
    return {
        "id": scenario["id"],
        "name": scenario["name"],
        "session_id": session_id,
        "passed": not failures,
        "failures": failures,
        "tool_names": tool_names,
        "tool_traces": all_tool_traces,
        "final_response": final_response.get(
            "response"
        ),
        "final_state": final_response.get(
            "state"
        ),
        "final_action": final_response.get(
            "action"
        ),
        "final_next_action": final_response.get(
            "next_action"
        ),
        "agent_mode": final_response.get(
            "agent_mode"
        ),
        "model_name": final_response.get(
            "model_name"
        ),
    }


def build_report(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    total = len(results)

    passed = sum(
        1
        for result in results
        if result["passed"]
    )

    failed = total - passed

    pass_rate = (
        round((passed / total) * 100, 2)
        if total
        else 0
    )

    return {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "total_scenarios": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": pass_rate,
        "results": results,
    }


def save_report(
    report: dict[str, Any],
) -> Path:
    REPORTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path = (
        REPORTS_DIR
        / "evaluation_report.json"
    )

    with report_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return report_path


def print_report(
    report: dict[str, Any],
) -> None:
    print()
    print("Mera Evaluation Summary")
    print("=" * 40)
    print(
        f"Scenarios: {report['total_scenarios']}"
    )
    print(f"Passed:    {report['passed']}")
    print(f"Failed:    {report['failed']}")
    print(
        f"Pass rate: {report['pass_rate']}%"
    )
    print()

    for result in report["results"]:
     status = (
        "PASS"
        if result["passed"]
        else "FAIL"
    )

    print(
        f"[{status}] {result['name']}"
    )

    for failure in result["failures"]:
        print(f"       - {failure}")

    if not result["passed"]:
        print(
            "       Tools:",
            result.get("tool_names", []),
        )

        print(
            "       Action:",
            result.get("final_action"),
        )

        print(
            "       Response:",
            result.get("final_response"),
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the Mera hotel booking agent."
        )
    )

    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
    )

    arguments = parser.parse_args()

    scenarios = load_scenarios()

    with httpx.Client(
        timeout=arguments.timeout,
    ) as client:
        results = [
            run_scenario(
                client=client,
                api_url=arguments.api_url,
                scenario=scenario,
            )
            for scenario in scenarios
        ]

    report = build_report(results)
    report_path = save_report(report)

    print_report(report)

    print()
    print(
        f"Report saved to: {report_path}"
    )


if __name__ == "__main__":
    main()