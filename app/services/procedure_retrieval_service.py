"""Procedure retrieval service interfaces and fake implementation."""

from typing import Protocol

from app.schemas.procedure import ProcedureSource

__all__ = ["ProcedureRetrievalService", "FakeProcedureRetrievalService"]


class ProcedureRetrievalService(Protocol):
    """Interface for retrieving procedure evidence sources."""

    async def retrieve(
        self, query: str, lang_mode: str, limit: int = 3
    ) -> list[ProcedureSource]:
        """Retrieve source documents relevant to the procedure query."""
        ...


class FakeProcedureRetrievalService:
    """Deterministic fake retriever for Sprint2 minimal implementation."""

    async def retrieve(
        self, query: str, lang_mode: str, limit: int = 3
    ) -> list[ProcedureSource]:
        """Return canned sources for known keywords, empty otherwise."""
        _ = lang_mode
        normalized_query = query.replace(" ", "")
        has_certificate_keyword = (
            "在学証明書" in normalized_query or "証明書" in normalized_query
        )
        if not has_certificate_keyword:
            return []

        sources = [
            ProcedureSource(
                title="証明書発行案内",
                section="申請方法",
                snippet="在学証明書は証明書自動発行機で申請できます。",
                source_id="doc_012_c03",
            )
        ]
        return sources[:limit]
