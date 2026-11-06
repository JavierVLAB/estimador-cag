"""turn_index counts every turn the session processed, not the window size."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.sessions.store import SessionStore

FORM = {
    "transcript": "Refining the scope of the CRM project for the sales team.",
    "project_type": "web_saas",
    "detail_level": "medium",
    "output_format": "phases_table",
}


def test_turn_index_keeps_growing_past_the_window(
    conversational_client: tuple[TestClient, SessionStore],
) -> None:
    client, _store = conversational_client
    session_id = client.post("/sessions").json()["session_id"]

    indexes = []
    for n in range(10):
        response = client.post(
            f"/sessions/{session_id}/estimate",
            data={**FORM, "transcript": f"Turn {n}: {FORM['transcript']}"},
        )
        assert response.status_code == 200, response.text
        indexes.append(response.json()["observation"]["turn_index"])

    assert indexes == list(range(1, 11))
