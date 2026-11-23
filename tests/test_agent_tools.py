from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from app.agent.tools import TOOLS, AgentToolbox, calculate_estimate, summarize_observation


def _assert_strict(schema: dict) -> None:
    """Strict mode: every object lists all its properties as required and forbids extras."""
    if schema.get("type") == "object" or "properties" in schema:
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])
        for child in schema["properties"].values():
            _assert_strict(child)
    if "items" in schema:
        _assert_strict(schema["items"])


@pytest.mark.parametrize("tool", TOOLS, ids=lambda tool: tool["name"])
def test_tools_are_flat_strict_responses_schemas(tool: dict) -> None:
    assert set(tool) == {"type", "name", "description", "parameters", "strict"}
    assert tool["type"] == "function"
    assert tool["strict"] is True
    _assert_strict(tool["parameters"])


def test_calculate_estimate_uses_median_plus_contingency_and_flags_empty() -> None:
    result = calculate_estimate(
        [
            {"name": "Auth", "reference_amounts": [100.0, 120.0, 400.0]},
            {"name": "SAP", "reference_amounts": []},
        ]
    )

    auth, sap = result["components"]
    assert auth == {
        "name": "Auth",
        "reference_count": 3,
        "estimated_hours": 138.0,
        "unbudgeted": False,
    }
    assert sap["estimated_hours"] == 0.0
    assert sap["unbudgeted"] is True
    assert result["total_hours"] == 138.0
    assert "unbudgeted: SAP" in result["summary"]


def _row(chunk_id: int, sector: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=chunk_id,
        document_id=1,
        chunk_type="component",
        content=f"[Project: p]\n\nComponent: Comp {chunk_id}\nDescription: Does {chunk_id}",
        metadata_={
            "budget_id": f"BUD-{chunk_id}",
            "client_sector": sector,
            "year": 2024,
            "complexity": "high",
            "estimated_hours": 10 * chunk_id,
        },
        distance=0.1 * chunk_id,
    )


class _FakeSession:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self.rows = rows
        self.sql: list[str] = []

    async def execute(self, statement):
        self.sql.append(str(statement.compile(dialect=postgresql.dialect())))
        return SimpleNamespace(all=lambda: self.rows[: statement._limit])


class _FakeEmbedder:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def embed_one(self, text: str) -> list[float]:
        self.texts.append(text)
        return [0.1]


async def test_search_budgets_wraps_hybrid_search_and_maps_items() -> None:
    session = _FakeSession([_row(i, "finance") for i in range(1, 8)])
    embedder = _FakeEmbedder()

    result = await AgentToolbox(session, embedder).execute(
        "search_budgets", {"reason": "r", "query": "auth backend", "filters": {"sector": None}}
    )

    assert embedder.texts == ["auth backend"]
    assert any("@@" in sql for sql in session.sql), "the lexical branch must run (hybrid)"
    assert result["count"] == 5
    assert result["items"][0] == {
        "chunk_id": 1,
        "budget_id": "BUD-1",
        "component": "Comp 1",
        "sector": "finance",
        "year": 2024,
        "complexity": "high",
        "estimated_hours": 10,
        "content_preview": "Does 1",
    }


async def test_search_budgets_sector_filter_keeps_only_that_sector() -> None:
    rows = [_row(i, "finance" if i % 2 else "industrial") for i in range(1, 9)]
    toolbox = AgentToolbox(_FakeSession(rows), _FakeEmbedder())

    result = await toolbox.search_budgets("q", {"sector": "industrial"})

    assert [item["budget_id"] for item in result["items"]] == ["BUD-2", "BUD-4", "BUD-6", "BUD-8"]


async def test_unknown_tool_returns_error() -> None:
    result = await AgentToolbox(_FakeSession([]), _FakeEmbedder()).execute("nope", {})

    assert "error" in result
    assert summarize_observation("nope", result).startswith("error")
