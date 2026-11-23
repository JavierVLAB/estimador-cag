"""Run the estimation agent on a transcript and print its step-by-step trace.

    docker compose run --rm -v ./odd:/app/odd estimator python -m scripts.run_agent \\
        data/session_12/sample_transcript_complex.txt --model gpt-5 --effort medium \\
        --out odd/s12/trace_complex.txt

Debug the loop cheaply first with ``--model gpt-5-mini`` and the simple transcript.
Next to the text trace, ``--out`` also writes the full result as JSON.
"""

import argparse
import asyncio
import json
from pathlib import Path

from app.agent.loop import DEFAULT_MAX_ITERATIONS, run_agent
from app.agent.schemas import AgentResult
from app.agent.tools import AgentToolbox
from app.dependencies import get_openai_client
from app.embedding_pipeline.database import get_sessionmaker
from app.embedding_pipeline.embedder import OpenAIEmbedder

RULE = "=" * 78


def _indent(text: str) -> str:
    return text.replace("\n", "\n               ")


def format_trace(result: AgentResult, *, transcript: str, model: str, effort: str) -> str:
    lines = [RULE, "AGENT TRACE", RULE, f"transcript: {transcript}"]
    lines.append(f"model: {model} | effort: {effort}\n")
    for step in result.trace:
        lines.append(f"STEP {step.step}  (turn {step.iteration})")
        lines.append(f"  reasoning:   {_indent(step.reasoning or '(no summary emitted)')}")
        lines.append(f"  decision:    {_indent(step.reason)}")
        lines.append(
            f"  action:      {step.tool}({json.dumps(step.arguments, ensure_ascii=False)})"
        )
        lines.append(f"  observation: {_indent(step.observation)}\n")

    lines += [RULE, "RESULT", RULE]
    lines.append(f"status: {result.status} after {result.iterations} model turns")
    lines.append(
        f"tokens: input={result.input_tokens} output={result.output_tokens} "
        f"(reasoning={result.reasoning_tokens})"
    )
    tool_calls = [step.tool for step in result.trace]
    lines.append(
        f"tool calls: search_budgets={tool_calls.count('search_budgets')} "
        f"calculate_estimate={tool_calls.count('calculate_estimate')}\n"
    )
    if result.estimate is not None:
        estimate = result.estimate
        lines.append(f"project: {estimate.project_summary}")
        for component in estimate.components:
            flag = "  [UNBUDGETED]" if component.unbudgeted else ""
            refs = ", ".join(component.reference_budget_ids) or "-"
            lines.append(f"  - {component.name}: {component.estimated_hours}h (refs: {refs}){flag}")
        lines.append(f"total: {estimate.total_hours}h")
        lines.append("assumptions:")
        lines += [f"  - {item}" for item in estimate.assumptions]
    else:
        lines.append(f"final text: {result.final_text}")
    if result.last_calculation is not None:
        lines.append(f"\nlast calculate_estimate: {result.last_calculation['summary']}")
    return "\n".join(lines)


async def main(args: argparse.Namespace) -> None:
    transcript = Path(args.transcript).read_text(encoding="utf-8")
    client = get_openai_client()
    async with get_sessionmaker()() as session:
        toolbox = AgentToolbox(session, OpenAIEmbedder(client))
        result = await run_agent(
            client,
            transcript,
            toolbox,
            model=args.model,
            effort=args.effort,
            max_iterations=args.max_iterations,
        )
    text = format_trace(result, transcript=args.transcript, model=args.model, effort=args.effort)
    print(text)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        out.with_suffix(".json").write_text(
            result.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("transcript")
    parser.add_argument("--model", default="gpt-5-mini")
    parser.add_argument("--effort", default="medium", choices=["minimal", "low", "medium", "high"])
    parser.add_argument("--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS)
    parser.add_argument("--out")
    asyncio.run(main(parser.parse_args()))
