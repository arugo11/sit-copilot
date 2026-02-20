"""Unit tests for procedure QA service."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.qa_turn import QATurn
from app.schemas.procedure import ProcedureAskRequest, ProcedureSource
from app.services.procedure_answerer_service import ProcedureAnswerDraft
from app.services.procedure_qa_service import SqlAlchemyProcedureQAService


class StubRetriever:
    """Stub retriever returning pre-defined sources."""

    def __init__(self, sources: list[ProcedureSource]) -> None:
        self._sources = sources

    async def retrieve(
        self, query: str, lang_mode: str, limit: int = 3
    ) -> list[ProcedureSource]:
        _ = (query, lang_mode, limit)
        return self._sources


class SpyAnswerer:
    """Spy answerer tracking invocation count."""

    def __init__(self, draft: ProcedureAnswerDraft) -> None:
        self._draft = draft
        self.call_count = 0

    async def answer(
        self, query: str, lang_mode: str, sources: list[ProcedureSource]
    ) -> ProcedureAnswerDraft:
        _ = (query, lang_mode, sources)
        self.call_count += 1
        return self._draft


@pytest.mark.asyncio
async def test_ask_with_sources_returns_answer_and_persists_turn(
    db_session: AsyncSession,
) -> None:
    """Service should answer with sources and persist qa_turn for evidence path."""
    sources = [
        ProcedureSource(
            title="証明書発行案内",
            section="申請方法",
            snippet="在学証明書は証明書発行機で発行できます。",
            source_id="doc_012_c03",
        )
    ]
    retriever = StubRetriever(sources)
    answerer = SpyAnswerer(
        ProcedureAnswerDraft(
            answer="在学証明書は証明書発行機で発行できます。",
            confidence="high",
            action_next="学生証を持って証明書発行機を利用してください。",
        )
    )
    service = SqlAlchemyProcedureQAService(
        db=db_session, retriever=retriever, answerer=answerer
    )

    response = await service.ask(
        ProcedureAskRequest(query="在学証明書はどこですか。", lang_mode="ja")
    )

    assert response.sources != []
    assert response.fallback == ""
    assert response.confidence == "high"
    assert answerer.call_count == 1

    result = await db_session.execute(
        select(QATurn).where(QATurn.question == "在学証明書はどこですか。")
    )
    qa_turn = result.scalar_one_or_none()
    assert qa_turn is not None
    assert qa_turn.feature == "procedure_qa"
    assert qa_turn.session_id is None
    assert qa_turn.verifier_supported is False
    assert qa_turn.latency_ms >= 0
    assert qa_turn.citations_json == [sources[0].model_dump()]
    assert qa_turn.retrieved_chunk_ids_json == ["doc_012_c03"]


@pytest.mark.asyncio
async def test_ask_without_sources_returns_fallback_and_does_not_call_answerer(
    db_session: AsyncSession,
) -> None:
    """Service should return fallback and skip answerer for no-evidence path."""
    retriever = StubRetriever([])
    answerer = SpyAnswerer(
        ProcedureAnswerDraft(
            answer="unused",
            confidence="medium",
            action_next="unused",
        )
    )
    service = SqlAlchemyProcedureQAService(
        db=db_session, retriever=retriever, answerer=answerer
    )

    response = await service.ask(
        ProcedureAskRequest(query="未知の質問", lang_mode="ja")
    )

    assert response.sources == []
    assert response.confidence == "low"
    assert response.fallback != ""
    assert answerer.call_count == 0

    result = await db_session.execute(
        select(QATurn).where(QATurn.question == "未知の質問")
    )
    qa_turn = result.scalar_one_or_none()
    assert qa_turn is not None
    assert qa_turn.feature == "procedure_qa"
    assert qa_turn.verifier_supported is False
    assert qa_turn.latency_ms >= 0
    assert qa_turn.citations_json == []
    assert qa_turn.retrieved_chunk_ids_json == []
