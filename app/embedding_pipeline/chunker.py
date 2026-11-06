"""Structural chunking for normalized software-budget JSON documents."""

import tiktoken

from app.embedding_pipeline.schemas import Budget, BudgetComponent, Chunk


EMBEDDING_MODEL = "text-embedding-3-small"


class JSONStructuralChunker:
    """Convert every budget component into one contextualized embedding chunk."""

    def __init__(self) -> None:
        self._encoding = tiktoken.encoding_for_model(EMBEDDING_MODEL)

    def chunk(self, budgets: list[Budget]) -> list[Chunk]:
        """Return one token-counted chunk per component, preserving input order."""
        return [
            self._chunk_component(budget, component)
            for budget in budgets
            for component in budget.components
        ]

    def _chunk_component(self, budget: Budget, component: BudgetComponent) -> Chunk:
        text = self._format_text(budget, component)
        return Chunk(
            chunk_id=f"{budget.budget_id}::{component.component_id}",
            text=text,
            metadata={
                "budget_id": budget.budget_id,
                "component_id": component.component_id,
                "client_sector": budget.client_metadata.sector,
                "main_technology": budget.main_technology,
                "year": budget.year,
                "complexity": component.complexity,
                "estimated_hours": component.estimated_hours,
            },
            token_count=len(self._encoding.encode(text)),
        )

    @staticmethod
    def _format_text(budget: Budget, component: BudgetComponent) -> str:
        return "\n".join(
            (
                f"[Project: {budget.project_summary}]",
                "[Client sector: "
                f"{budget.client_metadata.sector} | Year: {budget.year} | "
                f"Main tech: {budget.main_technology}]",
                "",
                f"Component: {component.name}",
                f"Description: {component.description}",
                f"Tech stack: {', '.join(component.tech_stack)}",
                f"Complexity: {component.complexity}",
                f"Estimated hours: {component.estimated_hours}",
            )
        )
