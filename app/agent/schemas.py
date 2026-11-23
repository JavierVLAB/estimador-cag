"""Final estimate, trace steps and result of the estimation agent."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class _Strict(BaseModel):
    # extra="forbid" emits additionalProperties: false, required by strict JSON Schema.
    model_config = ConfigDict(extra="forbid")


class EstimateComponent(_Strict):
    name: str
    description: str
    reference_budget_ids: list[str]
    estimated_hours: float
    unbudgeted: bool


class AgentEstimate(_Strict):
    """Structured estimate the agent returns once it stops calling tools."""

    project_summary: str
    components: list[EstimateComponent]
    total_hours: float
    assumptions: list[str]


class TraceStep(BaseModel):
    """One tool call: why the model made it, what it ran and what it saw."""

    step: int
    iteration: int
    reasoning: str
    reason: str
    tool: str
    arguments: dict[str, Any]
    observation: str
    result: dict[str, Any]


class AgentResult(BaseModel):
    status: Literal["completed", "max_iterations", "invalid_output"]
    iterations: int
    estimate: AgentEstimate | None
    final_text: str
    trace: list[TraceStep]
    last_calculation: dict[str, Any] | None
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int


def estimate_format() -> dict[str, Any]:
    """``text.format`` for the Responses API so the final answer is an AgentEstimate."""
    return {
        "type": "json_schema",
        "name": "agent_estimate",
        "schema": AgentEstimate.model_json_schema(),
        "strict": True,
    }
