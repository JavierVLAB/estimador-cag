import json
from types import SimpleNamespace

from app.agent.loop import run_agent
from app.agent.tools import calculate_estimate

FINAL = {
    "project_summary": "Auth backend",
    "components": [
        {
            "name": "Auth",
            "description": "OAuth backend",
            "reference_budget_ids": ["BUD-1"],
            "estimated_hours": 138.0,
            "unbudgeted": False,
        }
    ],
    "total_hours": 138.0,
    "assumptions": [],
}


def _call(call_id: str, name: str, arguments: dict) -> SimpleNamespace:
    return SimpleNamespace(
        type="function_call", call_id=call_id, name=name, arguments=json.dumps(arguments)
    )


def _reasoning(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="reasoning", summary=[SimpleNamespace(text=text)])


def _response(response_id: str, output: list, output_text: str = "") -> SimpleNamespace:
    usage = SimpleNamespace(
        input_tokens=10, output_tokens=5, output_tokens_details=SimpleNamespace(reasoning_tokens=2)
    )
    return SimpleNamespace(id=response_id, output=output, output_text=output_text, usage=usage)


class _FakeClient:
    """Replays scripted responses and records every request."""

    def __init__(self, responses: list) -> None:
        self._responses = iter(responses)
        self.requests: list[dict] = []
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        return next(self._responses)


class _FakeTools:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def execute(self, name: str, arguments: dict) -> dict:
        self.calls.append((name, arguments))
        if name == "search_budgets":
            items = [
                {"budget_id": "BUD-1", "component": "C", "sector": "s", "estimated_hours": 120}
            ]
            return {"query": arguments["query"], "count": 1, "items": items}
        return calculate_estimate(arguments["components"])


SEARCH_ARGS = {"reason": "need auth refs", "query": "auth", "filters": {"sector": None}}
CALC_ARGS = {"reason": "all found", "components": [{"name": "Auth", "reference_amounts": [120]}]}


async def test_loop_runs_tools_chains_call_ids_and_records_trace() -> None:
    client = _FakeClient(
        [
            _response(
                "r1",
                [
                    _reasoning("Two components."),
                    _call("c1", "search_budgets", SEARCH_ARGS),
                    _call("c2", "search_budgets", {**SEARCH_ARGS, "query": "mobile"}),
                ],
            ),
            _response("r2", [_call("c3", "calculate_estimate", CALC_ARGS)]),
            _response("r3", [], output_text=json.dumps(FINAL)),
        ]
    )
    tools = _FakeTools()

    result = await run_agent(client, "transcript", tools, model="m", effort="low")

    assert result.status == "completed"
    assert result.iterations == 3
    assert result.estimate.total_hours == 138.0
    assert [name for name, _ in tools.calls] == [
        "search_budgets",
        "search_budgets",
        "calculate_estimate",
    ]

    first, second, third = client.requests
    assert first["previous_response_id"] is None
    assert first["input"] == [{"role": "user", "content": "transcript"}]
    assert first["reasoning"] == {"effort": "low", "summary": "auto"}
    assert second["previous_response_id"] == "r1"
    assert [item["call_id"] for item in second["input"]] == ["c1", "c2"]
    assert all(item["type"] == "function_call_output" for item in second["input"])
    assert third["previous_response_id"] == "r2"
    assert [item["call_id"] for item in third["input"]] == ["c3"]

    steps = result.trace
    assert [step.tool for step in steps] == [
        "search_budgets",
        "search_budgets",
        "calculate_estimate",
    ]
    assert steps[0].reasoning == "Two components."
    assert "STEP 1" in steps[1].reasoning
    assert steps[0].reason == "need auth refs"
    assert "reason" not in steps[0].arguments
    assert steps[0].observation.startswith("1 items")
    assert result.last_calculation["total_hours"] == 138.0
    assert result.input_tokens == 30


async def test_loop_stops_at_max_iterations() -> None:
    looping = [
        _response(f"r{i}", [_call(f"c{i}", "search_budgets", SEARCH_ARGS)]) for i in range(5)
    ]
    client = _FakeClient(looping)

    result = await run_agent(client, "t", _FakeTools(), model="m", max_iterations=3)

    assert result.status == "max_iterations"
    assert len(client.requests) == 3
    assert result.estimate is None


async def test_loop_reports_tool_errors_to_the_model() -> None:
    class _Broken(_FakeTools):
        async def execute(self, name, arguments):
            raise RuntimeError("db down")

    client = _FakeClient(
        [
            _response("r1", [_call("c1", "search_budgets", SEARCH_ARGS)]),
            _response("r2", [], output_text="not json"),
        ]
    )

    result = await run_agent(client, "t", _Broken(), model="m")

    assert "db down" in json.loads(client.requests[1]["input"][0]["output"])["error"]
    assert result.status == "invalid_output"
