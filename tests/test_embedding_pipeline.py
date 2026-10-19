import tiktoken

from app.embedding_pipeline.chunker import JSONStructuralChunker
from app.embedding_pipeline.schemas import Budget


def _budget() -> Budget:
    return Budget.model_validate(
        {
            "budget_id": "BUD-2024-014",
            "client_metadata": {
                "name": "FintechCorp",
                "sector": "finance",
                "country": "ES",
            },
            "project_summary": "Mobile banking API with OAuth 2.0 authentication",
            "main_technology": "ruby_on_rails",
            "year": 2024,
            "total_estimated_hours": 480,
            "components": [
                {
                    "component_id": "AUTH-001",
                    "name": "OAuth 2.0 authentication backend",
                    "description": "JWT session management with client rate limiting.",
                    "tech_stack": ["ruby_on_rails", "postgresql", "redis"],
                    "estimated_hours": 120,
                    "complexity": "high",
                    "dependencies": [],
                },
                {
                    "component_id": "API-002",
                    "name": "Account API",
                    "description": "REST API for customer account balances.",
                    "tech_stack": ["ruby_on_rails", "postgresql"],
                    "estimated_hours": 80,
                    "complexity": "medium",
                    "dependencies": ["AUTH-001"],
                },
            ],
        }
    )


def test_budget_schema_accepts_normalized_budget() -> None:
    budget = _budget()

    assert budget.client_metadata.sector == "finance"
    assert budget.components[1].dependencies == ["AUTH-001"]


def test_chunker_makes_one_contextualized_chunk_per_component() -> None:
    chunks = JSONStructuralChunker().chunk([_budget()])

    assert [chunk.chunk_id for chunk in chunks] == [
        "BUD-2024-014::AUTH-001",
        "BUD-2024-014::API-002",
    ]
    first = chunks[0]
    assert "Mobile banking API with OAuth 2.0 authentication" in first.text
    assert "Client sector: finance" in first.text
    assert "Year: 2024" in first.text
    assert "Main tech: ruby_on_rails" in first.text
    assert "OAuth 2.0 authentication backend" in first.text
    assert "JWT session management with client rate limiting." in first.text
    assert "ruby_on_rails, postgresql, redis" in first.text
    assert "Complexity: high" in first.text
    assert "Estimated hours: 120" in first.text
    assert first.metadata == {
        "budget_id": "BUD-2024-014",
        "component_id": "AUTH-001",
        "client_sector": "finance",
        "main_technology": "ruby_on_rails",
        "year": 2024,
        "complexity": "high",
        "estimated_hours": 120,
    }
    encoding = tiktoken.encoding_for_model("text-embedding-3-small")
    assert first.token_count == len(encoding.encode(first.text))
