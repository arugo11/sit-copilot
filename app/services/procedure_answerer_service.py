"""Procedure answerer service interfaces and fake implementation."""

from dataclasses import dataclass
from typing import Protocol

from app.schemas.procedure import ProcedureConfidence, ProcedureSource

__all__ = [
    "ProcedureAnswerDraft",
    "ProcedureAnswererService",
    "FakeProcedureAnswererService",
]


@dataclass(frozen=True)
class ProcedureAnswerDraft:
    """Answerer output before API response packaging."""

    answer: str
    confidence: ProcedureConfidence
    action_next: str


class ProcedureAnswererService(Protocol):
    """Interface for generating grounded procedure answers."""

    async def answer(
        self, query: str, lang_mode: str, sources: list[ProcedureSource]
    ) -> ProcedureAnswerDraft:
        """Generate an answer based on provided sources only."""
        ...


class FakeProcedureAnswererService:
    """Deterministic fake answerer for Sprint2 minimal implementation."""

    async def answer(
        self, query: str, lang_mode: str, sources: list[ProcedureSource]
    ) -> ProcedureAnswerDraft:
        """Generate a stable answer from first source."""
        _ = (query, lang_mode)
        primary = sources[0]
        return ProcedureAnswerDraft(
            answer=(f"公式案内では、{primary.snippet}"),
            confidence="high",
            action_next=(
                "学生証を持って証明書発行機を利用してください。"
                "発行時間は窓口案内も確認してください。"
            ),
        )
