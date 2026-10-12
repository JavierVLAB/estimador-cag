"""GET /sessions/{id} exposes summary and anchor text for MemoryDriftMetric."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.sessions.models import Message
from app.sessions.store import SessionStore


def test_session_snapshot_exposes_summary_and_anchor_text(
    conversational_client: tuple[TestClient, SessionStore],
) -> None:
    client, store = conversational_client
    session_id = client.post("/sessions").json()["session_id"]
    session = store.get(session_id)
    session.history.summary = "Budget locked at 30000 EUR."
    session.history.anchors.append(Message(role="user", content="Stack is Flutter."))

    snapshot = client.get(f"/sessions/{session_id}").json()

    assert snapshot["summary"] == "Budget locked at 30000 EUR."
    assert snapshot["anchors"] == ["Stack is Flutter."]
