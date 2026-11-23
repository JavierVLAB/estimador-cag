"""Hand-driven agent loop over the OpenAI Responses API.

Each turn the model either asks for tools (``function_call`` items) or answers. We
run every requested tool, send the results back as ``function_call_output`` items
with the same ``call_id``, chain the turn with ``previous_response_id`` and repeat
until the model answers without tool calls or ``max_iterations`` is reached.
"""

import json
from typing import Any, Protocol

import structlog
from pydantic import ValidationError

from app.agent.schemas import AgentEstimate, AgentResult, TraceStep, estimate_format
from app.agent.tools import TOOLS, summarize_observation

log = structlog.get_logger()

DEFAULT_MAX_ITERATIONS = 12

SYSTEM_PROMPT = """\
You are a senior software estimation consultant. You receive the transcript of a \
discovery meeting with a client and must produce an effort estimate in engineer-hours, \
grounded in the archive of past budgets.

Method:
1. Read the transcript and decompose the project into its distinct components.
2. For each component, use search_budgets to find comparable historical components.
3. Judge which results really match each component. Keep only the hours of relevant \
matches; if nothing relevant comes back, try one rephrased search before giving up.
4. Use calculate_estimate with all the components and their reference hours.
5. Answer with the final estimate. Take each component's hours and the total from \
calculate_estimate, list the budget ids you used, flag unbudgeted components, and \
state your assumptions, including any weak or missing references.

Never invent hours: every number must come from the tools.\
"""


class ToolExecutor(Protocol):
    async def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


def _reasoning_summary(response: Any) -> str:
    """Concatenated reasoning summaries of one response (empty if none were emitted)."""
    parts = [
        part.text
        for item in response.output
        if item.type == "reasoning"
        for part in (item.summary or [])
    ]
    return "\n".join(parts).strip()


async def run_agent(
    client: Any,
    transcript: str,
    tools: ToolExecutor,
    *,
    model: str,
    effort: str = "medium",
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> AgentResult:
    """Run the reason-act-observe loop and return the estimate with its trace."""
    trace: list[TraceStep] = []
    last_calculation: dict[str, Any] | None = None
    tokens = {"input": 0, "output": 0, "reasoning": 0}
    next_input: list[dict[str, Any]] = [{"role": "user", "content": transcript}]
    previous_response_id: str | None = None

    for iteration in range(1, max_iterations + 1):
        response = client.responses.create(
            model=model,
            instructions=SYSTEM_PROMPT,
            input=next_input,
            tools=TOOLS,
            reasoning={"effort": effort, "summary": "auto"},
            text={"format": estimate_format()},
            previous_response_id=previous_response_id,
        )
        usage = getattr(response, "usage", None)
        if usage is not None:
            tokens["input"] += usage.input_tokens
            tokens["output"] += usage.output_tokens
            details = getattr(usage, "output_tokens_details", None)
            tokens["reasoning"] += getattr(details, "reasoning_tokens", 0) or 0

        summary = _reasoning_summary(response)
        calls = [item for item in response.output if item.type == "function_call"]
        log.info("agent_turn", iteration=iteration, tool_calls=len(calls), response_id=response.id)

        if not calls:
            final_text = response.output_text
            try:
                estimate = AgentEstimate.model_validate_json(final_text)
                status = "completed"
            except ValidationError:
                log.warning("agent_invalid_output", iteration=iteration)
                estimate, status = None, "invalid_output"
            return AgentResult(
                status=status,
                iterations=iteration,
                estimate=estimate,
                final_text=final_text,
                trace=trace,
                last_calculation=last_calculation,
                input_tokens=tokens["input"],
                output_tokens=tokens["output"],
                reasoning_tokens=tokens["reasoning"],
            )

        first_step_of_turn = len(trace) + 1
        outputs: list[dict[str, Any]] = []
        for position, call in enumerate(calls):
            arguments = json.loads(call.arguments)
            try:
                result = await tools.execute(call.name, arguments)
            except Exception as exc:  # the model reads the error and can adapt
                log.warning("agent_tool_error", tool=call.name, error=str(exc))
                result = {"error": f"{type(exc).__name__}: {exc}"}
            if call.name == "calculate_estimate" and "error" not in result:
                last_calculation = result
            observation = summarize_observation(call.name, result)
            trace.append(
                TraceStep(
                    step=len(trace) + 1,
                    iteration=iteration,
                    reasoning=(
                        summary
                        if position == 0
                        else f"(parallel call in the same turn as STEP {first_step_of_turn})"
                    ),
                    reason=arguments.get("reason", ""),
                    tool=call.name,
                    arguments={k: v for k, v in arguments.items() if k != "reason"},
                    observation=observation,
                    result=result,
                )
            )
            log.info("agent_step", step=len(trace), tool=call.name, observation=observation)
            outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(result),
                }
            )
        next_input = outputs
        previous_response_id = response.id

    log.warning("agent_max_iterations", max_iterations=max_iterations)
    return AgentResult(
        status="max_iterations",
        iterations=max_iterations,
        estimate=None,
        final_text="",
        trace=trace,
        last_calculation=last_calculation,
        input_tokens=tokens["input"],
        output_tokens=tokens["output"],
        reasoning_tokens=tokens["reasoning"],
    )
