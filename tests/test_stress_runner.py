"""Smoke test of the stress runner against an in-process fake LLM.

The full runner orchestration (scenarios × sizes × repeats + CSV writer)
is exercised end-to-end with a FakeLLMWrapper, so that wiring bugs in the
``observation`` plumbing, the CSV schema, or the metric calls surface in
seconds without burning real LLM credit.
"""

from __future__ import annotations

import csv
from pathlib import Path

from app.schemas.estimation import DetailLevel, OutputFormat, ProjectType
from evals.stress.metrics import CostBudgetMetric, LatencyBudgetMetric
import evals.stress.run as stress_run
from app.schemas.estimation import TurnObservation
from evals.stress.run import _CSV_COLUMNS, _run_one_session
from evals.stress.scenarios import Scenario, ScenarioTurn


def _tiny_scenario() -> Scenario:
    """A scenario short enough to keep tests fast but long enough to exercise
    the sliding window + at least one drift evaluation post-turn-1."""

    # Build 20 minimally valid turns (the scenario dataclass enforces >=20).
    turns = [
        ScenarioTurn(
            transcript=(
                "We want a B2B SaaS called Nimbus for procurement teams. "
                "Stack: React + Postgres. Team of 3."
            ),
            fact_introduced="Nimbus",
            fact_field="project_name",
        )
    ]
    for i in range(2, 21):
        turns.append(
            ScenarioTurn(
                transcript=(
                    f"Turn {i}: add another feature, expand the scope a little. "
                    "Keep the same stack and team for now."
                ),
                fact_introduced=None,
            )
        )
    return Scenario(
        name="growing",
        project_type=ProjectType.WEB_SAAS,
        detail_level=DetailLevel.MEDIUM,
        output_format=OutputFormat.PHASES_TABLE,
        turns=turns,
    )


def test_runner_writes_csv_with_expected_columns_and_rows(
    conversational_client, tmp_path: Path
):
    """Walk 3 turns of a scripted session, validate CSV shape."""
    client, _store = conversational_client
    scenario = _tiny_scenario()
    # Truncate to 3 turns for speed — the scenario object enforces >=20 but
    # _run_one_session iterates whatever we give it via scenario.turns.
    object.__setattr__(scenario, "turns", scenario.turns[:3])

    csv_path = tmp_path / "smoke.csv"
    with csv_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        rows_written = _run_one_session(
            client=client,
            scenario=scenario,
            size_kb=0,
            repeat=0,
            latency_metric=LatencyBudgetMetric(budget_ms=60_000),
            cost_metric=CostBudgetMetric(budget_usd=10.0),
            writer=writer,
        )

    assert rows_written == 3
    with csv_path.open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 3
    # Every column is filled (apart from a few that are intentionally blank
    # in turn 1 — memory_drift_passed, which is empty for turn_index == 1).
    for row in rows:
        assert row["scenario"] == "growing"
        assert row["attachment_size_kb"] == "0"
        assert row["tracked_fact"] == "Nimbus"
        assert row["error"] == ""
        assert int(row["turn_index"]) >= 1
        assert int(row["messages_in_window"]) > 0
        assert row["latency_budget_passed"] == "True"
        assert row["cost_budget_passed"] == "True"

    # Turn 1 → drift column blank (trivial); turns 2 & 3 → must be filled.
    assert rows[0]["memory_drift_passed"] == ""
    assert rows[1]["memory_drift_passed"] in {"True", "False"}
    assert rows[2]["memory_drift_passed"] in {"True", "False"}


def test_runner_records_error_row_on_failure(conversational_client, tmp_path: Path):
    """If a turn raises, the runner records an error row and stops the session."""
    client, _store = conversational_client
    scenario = _tiny_scenario()
    # Replace turn 2's transcript with one short enough to trigger the
    # ``min_length=20`` validation on the form — that's a 422 from the API.
    bad_turn = ScenarioTurn(transcript="too short", fact_introduced=None)
    object.__setattr__(scenario, "turns", [scenario.turns[0], bad_turn, scenario.turns[2]])

    csv_path = tmp_path / "smoke.csv"
    with csv_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        rows_written = _run_one_session(
            client=client,
            scenario=scenario,
            size_kb=0,
            repeat=0,
            latency_metric=LatencyBudgetMetric(budget_ms=60_000),
            cost_metric=CostBudgetMetric(budget_usd=10.0),
            writer=writer,
            turn_retries=0,
        )

    assert rows_written == 2  # turn 1 ok + turn 2 errored, then aborted
    with csv_path.open() as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["error"] == ""
    assert rows[1]["error"] != ""
    assert "HTTPStatusError" in rows[1]["error"] or "422" in rows[1]["error"]


class _FakeClient:
    """Only the session-creation call is used; turns go through a patched
    ``_execute_turn``."""

    def post(self, url, **kwargs):
        class _Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"session_id": "s-1"}

        return _Resp()


def _observation(turn_index: int) -> TurnObservation:
    return TurnObservation(
        turn_index=turn_index,
        session_id="s-1",
        enriched_transcript_chars=10,
        attachments_total_chars=0,
        messages_in_window=2,
        anchors_count=0,
        summary_chars=0,
        tokens_in=1,
        tokens_out=1,
        cost_usd=0.001,
        latency_ms=10,
    )


def _run_with_fake(monkeypatch, tmp_path: Path, outcomes: list, turns: int, retries: int):
    """``outcomes`` is consumed one per ``_execute_turn`` call; an Exception
    instance is raised, anything else is returned as a success."""
    scenario = _tiny_scenario()
    object.__setattr__(scenario, "turns", scenario.turns[:turns])
    calls = iter(outcomes)
    successes = {"n": 0}

    def fake_execute(client, session_id, scenario, turn, files):
        outcome = next(calls)
        if isinstance(outcome, Exception):
            raise outcome
        successes["n"] += 1
        return _observation(successes["n"]), {"messages": []}, 5

    monkeypatch.setattr(stress_run, "_execute_turn", fake_execute)
    csv_path = tmp_path / "retry.csv"
    with csv_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        rows_written = _run_one_session(
            client=_FakeClient(),
            scenario=scenario,
            size_kb=0,
            repeat=0,
            latency_metric=LatencyBudgetMetric(budget_ms=60_000),
            cost_metric=CostBudgetMetric(budget_usd=10.0),
            writer=writer,
            turn_retries=retries,
        )
    with csv_path.open() as fh:
        rows = list(csv.DictReader(fh))
    return rows_written, rows


def test_failed_turn_is_retried_and_session_continues(monkeypatch, tmp_path: Path):
    rows_written, rows = _run_with_fake(
        monkeypatch,
        tmp_path,
        outcomes=[RuntimeError("502 boom"), "ok", "ok"],
        turns=2,
        retries=2,
    )
    assert rows_written == 3
    assert [r["attempt"] for r in rows] == ["1", "2", "1"]
    assert rows[0]["error"] != ""
    assert rows[1]["error"] == "" and rows[1]["turn_index"] == "1"
    assert rows[2]["error"] == "" and rows[2]["turn_index"] == "2"


def test_runner_prints_one_progress_line_per_attempt(monkeypatch, tmp_path: Path, capsys):
    _run_with_fake(
        monkeypatch,
        tmp_path,
        outcomes=[RuntimeError("502 boom"), "ok", "ok"],
        turns=2,
        retries=2,
    )
    lines = [line for line in capsys.readouterr().out.splitlines() if "turn" in line]
    assert len(lines) == 3
    assert "turn  1/2" in lines[0] and "FAILED" in lines[0]
    assert "turn  1/2" in lines[1] and "ok" in lines[1]
    assert "turn  2/2" in lines[2] and "ok" in lines[2]


def test_turn_failing_every_attempt_aborts_session(monkeypatch, tmp_path: Path):
    rows_written, rows = _run_with_fake(
        monkeypatch,
        tmp_path,
        outcomes=[RuntimeError("a"), RuntimeError("b"), RuntimeError("c"), "ok"],
        turns=3,
        retries=2,
    )
    assert rows_written == 3
    assert [r["attempt"] for r in rows] == ["1", "2", "3"]
    assert all(r["error"] != "" for r in rows)


# -- full fact tracker + competing facts (T4) --------------------------------


def _run_with_snapshots(monkeypatch, tmp_path: Path, scenario, snapshot_for_turn):
    """Run ``scenario`` with a patched ``_execute_turn``; ``snapshot_for_turn``
    maps the 1-based turn number to the snapshot the fake server returns."""
    counter = {"n": 0}

    def fake_execute(client, session_id, scenario, turn, files):
        counter["n"] += 1
        return _observation(counter["n"]), snapshot_for_turn(counter["n"]), 5

    monkeypatch.setattr(stress_run, "_execute_turn", fake_execute)
    csv_path = tmp_path / "t4.csv"
    with csv_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        _run_one_session(
            client=_FakeClient(),
            scenario=scenario,
            size_kb=0,
            repeat=0,
            latency_metric=LatencyBudgetMetric(budget_ms=60_000),
            cost_metric=CostBudgetMetric(budget_usd=10.0),
            writer=writer,
            turn_retries=0,
        )
    with csv_path.open() as fh:
        return list(csv.DictReader(fh))


def _scenario_with(turns: list[ScenarioTurn], competing=None) -> Scenario:
    scenario = _tiny_scenario()
    object.__setattr__(scenario, "turns", turns)
    object.__setattr__(scenario, "competing_facts", competing)
    return scenario


def test_fact_tracker_counts_every_earlier_fact(monkeypatch, tmp_path: Path):
    turns = [
        ScenarioTurn("t1" * 20, fact_introduced="Nimbus", fact_field="project_name"),
        ScenarioTurn("t2" * 20, fact_introduced="Okta", fact_field="technologies"),
        ScenarioTurn("t3" * 20, fact_introduced=None),
        ScenarioTurn("t4" * 20, fact_introduced="Okta", fact_field="technologies"),
        ScenarioTurn("t5" * 20, fact_introduced=None),
    ]
    snapshot = {"metadata": {"project_name": "Nimbus", "mentioned_technologies": []}}
    rows = _run_with_snapshots(
        monkeypatch, tmp_path, _scenario_with(turns), lambda n: snapshot
    )
    got = [(r["facts_tracked"], r["facts_recalled"], r["fact_recall"]) for r in rows]
    assert got == [
        ("0", "0", ""),  # nothing introduced before turn 1
        ("1", "1", "1.0"),  # Nimbus
        ("2", "1", "0.5"),  # Nimbus + Okta (missing)
        ("2", "1", "0.5"),  # Okta introduced at 2 and 4 -> deduped
        ("2", "1", "0.5"),
    ]
    # Turn-1 tracker keeps its old semantics.
    assert rows[0]["memory_drift_passed"] == ""
    assert rows[1]["memory_drift_passed"] == "True"
    assert rows[1]["tracked_fact"] == "Nimbus"


def test_competing_facts_report_where_each_value_appears(monkeypatch, tmp_path: Path):
    from evals.stress.scenarios import CompetingFacts

    turns = [ScenarioTurn(f"turn {i} " * 5, fact_introduced=None) for i in range(1, 5)]
    competing = CompetingFacts(
        old=("React Native",), new=("Flutter",), introduced_at_turn=3
    )

    def snapshot_for_turn(n):
        return {
            "summary": "stack was react native",
            "anchors": ["use Flutter"],
            "metadata": {"mentioned_technologies": ["Flutter", "React Native"]},
        }

    rows = _run_with_snapshots(
        monkeypatch, tmp_path, _scenario_with(turns, competing), snapshot_for_turn
    )
    assert [r["old_fact_in"] for r in rows] == ["", "", "summary|metadata", "summary|metadata"]
    assert [r["new_fact_in"] for r in rows] == ["", "", "anchors|metadata", "anchors|metadata"]


def test_competing_facts_empty_string_when_value_absent(monkeypatch, tmp_path: Path):
    from evals.stress.scenarios import CompetingFacts

    turns = [ScenarioTurn(f"turn {i} " * 5, fact_introduced=None) for i in range(1, 3)]
    competing = CompetingFacts(old=("30k",), new=("80k",), introduced_at_turn=1)
    rows = _run_with_snapshots(
        monkeypatch,
        tmp_path,
        _scenario_with(turns, competing),
        lambda n: {"metadata": {}},
    )
    assert [r["old_fact_in"] for r in rows] == ["", ""]
    assert [r["new_fact_in"] for r in rows] == ["", ""]


def test_scenarios_declare_competing_facts_and_tight_budget_needles():
    from evals.stress.scenarios import get_scenario

    assert get_scenario("growing").competing_facts is None
    pivot = get_scenario("pivot").competing_facts
    assert pivot.old == ("React Native",) and pivot.new == ("Flutter",)
    assert pivot.introduced_at_turn == 5
    contra = get_scenario("contradiction")
    assert contra.competing_facts.introduced_at_turn == 8
    assert "30000" in contra.competing_facts.old
    assert "80000" in contra.competing_facts.new
    assert contra.turns[2].fact_introduced == "30000"
    assert contra.turns[7].fact_introduced == "80000"
    assert contra.turns[8].fact_introduced == "80000"
