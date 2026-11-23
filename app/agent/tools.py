"""Tools of the estimation agent: flat Responses API schemas plus their implementations.

``search_budgets`` wraps the existing hybrid retrieval; ``calculate_estimate`` is a
deterministic cost model with no LLM call. Both take a ``reason`` argument so the
trace records why the model chose each action, even without reasoning summaries.
"""

import json
import statistics
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.search import RetrievedChunk, search

# Flat contingency buffer added to every component's central estimate.
CONTINGENCY_FACTOR = 0.15
SEARCH_TOP_K = 5
# Wider candidate pool so a sector filter still leaves results to return.
SEARCH_CANDIDATES_K = 20
SECTORS = ["finance", "ecommerce", "healthcare", "industrial"]
PREVIEW_CHARS = 220

REASON_PROPERTY = {
    "type": "string",
    "description": "One or two sentences on why you are calling this tool now. Shown in the trace.",
}

SEARCH_BUDGETS_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "search_budgets",
    "description": (
        "Search the archive of past software budgets for components similar to ONE "
        "component of the new project. Returns up to 5 historical components, each with "
        "its budget id, component name, client sector, year, complexity and the "
        "engineer-hours it was actually budgeted at. Call it once per component you "
        "identified in the transcript, with a focused query about that component only; "
        "do not combine several components in one query. The archive is written in "
        "English, so always write the query in English, even when the transcript is in "
        "another language. If the results do not match the component, you may search "
        "again with different wording."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "reason": REASON_PROPERTY,
            "query": {
                "type": "string",
                "description": (
                    "English description of a single component: what it does and its "
                    "key technical features, e.g. 'OAuth 2.0 authentication backend "
                    "with JWT sessions and per-client rate limiting'."
                ),
            },
            "filters": {
                "type": "object",
                "description": "Optional restrictions on the historical budgets returned.",
                "properties": {
                    "sector": {
                        "type": ["string", "null"],
                        "enum": [*SECTORS, None],
                        "description": (
                            "Only return budgets from this client sector. Use null unless "
                            "the sector clearly matters; the archive only covers these "
                            "four sectors."
                        ),
                    },
                },
                "required": ["sector"],
                "additionalProperties": False,
            },
        },
        "required": ["reason", "query", "filters"],
        "additionalProperties": False,
    },
    "strict": True,
}

CALCULATE_ESTIMATE_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "calculate_estimate",
    "description": (
        "Deterministically compute the effort estimate for a set of components from the "
        "historical hours you found with search_budgets. For each component it takes the "
        "median of its reference hours and adds a 15% contingency; a component with no "
        "references is costed at 0 hours and flagged as unbudgeted. Returns the "
        "per-component breakdown and the total hours. Call it after searching, passing "
        "every component of the project at once. Only pass hours that appeared in "
        "search results; never invent them. Leave reference_amounts empty when nothing "
        "relevant was found."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "reason": REASON_PROPERTY,
            "components": {
                "type": "array",
                "description": "Every component of the new project.",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Short name of the component in the new project.",
                        },
                        "reference_amounts": {
                            "type": "array",
                            "items": {"type": "number"},
                            "description": (
                                "Estimated hours of the relevant historical components "
                                "returned by search_budgets."
                            ),
                        },
                    },
                    "required": ["name", "reference_amounts"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["reason", "components"],
        "additionalProperties": False,
    },
    "strict": True,
}

TOOLS = [SEARCH_BUDGETS_TOOL, CALCULATE_ESTIMATE_TOOL]


def calculate_estimate(components: list[dict[str, Any]]) -> dict[str, Any]:
    """Cost each component from its reference hours (median + contingency), then total.

    The median resists a single outlier budget. Without references the component is
    costed at 0 and flagged, so nothing is invented and the agent can search again.
    """
    breakdown: list[dict[str, Any]] = []
    for component in components:
        refs = component.get("reference_amounts", [])
        if refs:
            hours = round(statistics.median(refs) * (1 + CONTINGENCY_FACTOR), 1)
        else:
            hours = 0.0
        breakdown.append(
            {
                "name": component["name"],
                "reference_count": len(refs),
                "estimated_hours": hours,
                "unbudgeted": not refs,
            }
        )
    total = round(sum(item["estimated_hours"] for item in breakdown), 1)
    unbudgeted = [item["name"] for item in breakdown if item["unbudgeted"]]
    summary = f"total={total}h across {len(breakdown)} components"
    if unbudgeted:
        summary += f"; unbudgeted: {', '.join(unbudgeted)}"
    return {"components": breakdown, "total_hours": total, "summary": summary}


class Embedder(Protocol):
    def embed_one(self, text: str) -> list[float]: ...


def _field(content: str, label: str) -> str:
    """Value of a ``Label: value`` line of a chunk, or an empty string."""
    prefix = f"{label}: "
    for line in content.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :]
    return ""


def _to_item(chunk: RetrievedChunk) -> dict[str, Any]:
    metadata = chunk.metadata_
    return {
        "chunk_id": chunk.id,
        "budget_id": metadata.get("budget_id"),
        "component": _field(chunk.content, "Component"),
        "sector": metadata.get("client_sector"),
        "year": metadata.get("year"),
        "complexity": metadata.get("complexity"),
        "estimated_hours": metadata.get("estimated_hours"),
        "content_preview": _field(chunk.content, "Description")[:PREVIEW_CHARS],
    }


class AgentToolbox:
    """Executes the agent's tool calls against the real retrieval pipeline."""

    def __init__(self, session: AsyncSession, embedder: Embedder) -> None:
        self._session = session
        self._embedder = embedder

    async def search_budgets(self, query: str, filters: dict[str, Any]) -> dict[str, Any]:
        sector = filters.get("sector")
        chunks = await search(
            self._session,
            query,
            self._embedder.embed_one(query),
            k=SEARCH_CANDIDATES_K if sector else SEARCH_TOP_K,
            mode="hybrid",
        )
        if sector:
            chunks = [c for c in chunks if c.metadata_.get("client_sector") == sector]
        items = [_to_item(chunk) for chunk in chunks[:SEARCH_TOP_K]]
        return {"query": query, "count": len(items), "items": items}

    async def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Run one tool call; unknown tools come back as an error the model can read."""
        if name == "search_budgets":
            return await self.search_budgets(arguments["query"], arguments.get("filters") or {})
        if name == "calculate_estimate":
            return calculate_estimate(arguments["components"])
        return {"error": f"unknown tool {name!r}"}


def summarize_observation(name: str, result: dict[str, Any]) -> str:
    """One-line summary of a tool result for the trace."""
    if "error" in result:
        return f"error: {result['error']}"
    if name == "search_budgets":
        if not result["items"]:
            return "no historical items found"
        hits = "; ".join(
            f"{item['budget_id']} '{item['component']}' ({item['sector']}) "
            f"{item['estimated_hours']}h"
            for item in result["items"]
        )
        return f"{result['count']} items: {hits}"
    if name == "calculate_estimate":
        return result["summary"]
    return json.dumps(result)[:300]
