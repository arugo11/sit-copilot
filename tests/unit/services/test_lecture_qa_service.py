"""Unit tests for lecture QA service."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lecture_session import LectureSession
from app.models.qa_turn import QATurn
from app.schemas.lecture_qa import (
    LectureSource,
)
from app.services.lecture_answerer_service import LectureAnswerDraft
from app.services.lecture_followup_service import FollowupResolution
from app.services.lecture_live_service import LectureSessionNotFoundError
from app.services.lecture_qa_service import SqlAlchemyLectureQAService
from app.services.lecture_verifier_service import LectureVerificationResult


class MockRetriever:
    """Mock retriever returning pre-defined sources."""

    def __init__(self, sources: list[LectureSource] | None = None) -> None:
        self._sources = sources or []
        self.retrieve_calls: list[dict] = []

    async def retrieve(
        self,
        session_id: str,
        query: str,
        mode: str,
        top_k: int,
        context_window: int,
    ) -> list[LectureSource]:
        self.retrieve_calls.append(
            {
                "session_id": session_id,
                "query": query,
                "mode": mode,
                "top_k": top_k,
                "context_window": context_window,
            }
        )
        return self._sources


class MockAnswerer:
    """Mock answerer returning pre-defined draft."""

    def __init__(self, draft: LectureAnswerDraft | None = None) -> None:
        self._draft = draft or LectureAnswerDraft(
            answer="Test answer.",
            confidence="high",
            action_next="Action.",
        )
        self.answer_calls: list[dict] = []

    async def answer(
        self,
        question: str,
        lang_mode: str,
        sources: list[LectureSource],
        history: str,
    ) -> LectureAnswerDraft:
        self.answer_calls.append(
            {
                "question": question,
                "lang_mode": lang_mode,
                "sources": sources,
                "history": history,
            }
        )
        return self._draft


class MockVerifier:
    """Mock verifier returning pre-defined result."""

    def __init__(
        self,
        passed: bool = True,
        summary: str = "Verified.",
        can_repair: bool = False,
        repaired_answer: str | None = None,
    ) -> None:
        self._passed = passed
        self._summary = summary
        self._can_repair = can_repair
        self._repaired_answer = repaired_answer
        self.verify_calls: list[dict] = []
        self.repair_calls: list[dict] = []

    async def verify(
        self,
        question: str,
        answer: str,
        sources: list[LectureSource],
    ) -> LectureVerificationResult:
        self.verify_calls.append(
            {
                "question": question,
                "answer": answer,
                "sources": sources,
            }
        )
        return LectureVerificationResult(
            passed=self._passed,
            summary=self._summary,
            unsupported_claims=[] if self._passed else ["Claim 1"],
        )

    async def repair_answer(
        self,
        question: str,
        answer: str,
        sources: list[LectureSource],
        unsupported_claims: list[str],
    ) -> str | None:
        self.repair_calls.append(
            {
                "question": question,
                "answer": answer,
                "sources": sources,
                "unsupported_claims": unsupported_claims,
            }
        )
        return self._repaired_answer if self._can_repair else None


class MockFollowup:
    """Mock followup service returning pre-defined resolution."""

    def __init__(
        self,
        standalone_query: str = "Resolved query",
        history_context: str = "History context",
    ) -> None:
        self._standalone_query = standalone_query
        self._history_context = history_context
        self.resolve_calls: list[dict] = []

    async def resolve_query(
        self,
        session_id: str,
        user_id: str,
        question: str,
        history_turns: int,
    ) -> FollowupResolution:
        self.resolve_calls.append(
            {
                "session_id": session_id,
                "user_id": user_id,
                "question": question,
                "history_turns": history_turns,
            }
        )
        return FollowupResolution(
            standalone_query=self._standalone_query,
            history_context=self._history_context,
        )


async def _seed_lecture_session(
    db_session: AsyncSession,
    *,
    session_id: str = "session_123",
    user_id: str = "user_1",
) -> None:
    """Seed an owned lecture session for QA ownership checks."""
    db_session.add(
        LectureSession(
            id=session_id,
            user_id=user_id,
            course_name="Test Course",
            status="active",
            started_at=datetime.now(UTC),
        )
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_ask_with_sources_returns_answer_and_persists_turn(
    db_session: AsyncSession,
) -> None:
    """Service should answer with sources and persist qa_turn."""
    await _seed_lecture_session(db_session)
    sources = [
        LectureSource(
            chunk_id="speech_1",
            type="speech",
            text="Test content",
            bm25_score=5.0,
        )
    ]
    retriever = MockRetriever(sources)
    answerer = MockAnswerer(
        LectureAnswerDraft(
            answer="Test answer.",
            confidence="high",
            action_next="Action.",
        )
    )
    verifier = MockVerifier(passed=True, summary="All claims verified.")
    followup = MockFollowup()

    service = SqlAlchemyLectureQAService(
        db=db_session,
        retriever=retriever,
        answerer=answerer,
        verifier=verifier,
        followup=followup,
    )

    response = await service.ask(
        session_id="session_123",
        user_id="user_1",
        question="What is this?",
        lang_mode="ja",
        retrieval_mode="source-only",
        top_k=5,
        context_window=1,
    )

    assert response.answer == "Test answer."
    assert response.confidence == "high"
    assert len(response.sources) == 1
    assert response.sources[0].chunk_id == "speech_1"
    assert response.verification_summary == "All claims verified."
    assert response.fallback == ""
    assert len(retriever.retrieve_calls) == 1
    assert len(answerer.answer_calls) == 1
    assert len(verifier.verify_calls) == 1

    # Verify persistence
    await db_session.flush()
    result = await db_session.execute(
        select(QATurn).where(
            QATurn.session_id == "session_123",
            QATurn.feature == "lecture_qa",
        )
    )
    qa_turn = result.scalar_one_or_none()
    assert qa_turn is not None
    assert qa_turn.question == "What is this?"
    assert qa_turn.answer == "Test answer."
    assert qa_turn.confidence == "high"
    assert qa_turn.verifier_supported is True
    assert qa_turn.latency_ms >= 0
    assert qa_turn.citations_json == [sources[0].model_dump()]
    assert qa_turn.retrieved_chunk_ids_json == ["speech_1"]


@pytest.mark.asyncio
async def test_ask_without_sources_returns_fallback_and_persists_turn(
    db_session: AsyncSession,
) -> None:
    """Service should return fallback and skip answerer for no-source path."""
    await _seed_lecture_session(db_session)
    retriever = MockRetriever([])  # No sources
    answerer = MockAnswerer()
    verifier = MockVerifier()
    followup = MockFollowup()

    service = SqlAlchemyLectureQAService(
        db=db_session,
        retriever=retriever,
        answerer=answerer,
        verifier=verifier,
        followup=followup,
    )

    response = await service.ask(
        session_id="session_123",
        user_id="user_1",
        question="Unknown question",
        lang_mode="ja",
        retrieval_mode="source-only",
        top_k=5,
        context_window=1,
    )

    assert response.answer == "講義資料に該当する情報が見つかりませんでした。"
    assert response.confidence == "low"
    assert response.sources == []
    assert response.fallback is not None
    assert len(retriever.retrieve_calls) == 1
    assert len(answerer.answer_calls) == 0  # Answerer not called
    assert len(verifier.verify_calls) == 0  # Verifier not called

    # Verify persistence
    await db_session.flush()
    result = await db_session.execute(
        select(QATurn).where(
            QATurn.session_id == "session_123",
            QATurn.feature == "lecture_qa",
        )
    )
    qa_turn = result.scalar_one_or_none()
    assert qa_turn is not None
    assert qa_turn.question == "Unknown question"
    assert qa_turn.citations_json == []
    assert qa_turn.retrieved_chunk_ids_json == []


@pytest.mark.asyncio
async def test_ask_with_verification_failure_triggers_repair(
    db_session: AsyncSession,
) -> None:
    """Service should attempt repair when verification fails."""
    await _seed_lecture_session(db_session)
    sources = [
        LectureSource(
            chunk_id="speech_1",
            type="speech",
            text="Test content",
            bm25_score=5.0,
        )
    ]
    retriever = MockRetriever(sources)
    answerer = MockAnswerer(
        LectureAnswerDraft(
            answer="Original answer.",
            confidence="high",
            action_next="Action.",
        )
    )
    # First verification fails, but repair succeeds
    verifier = MockVerifier(
        passed=False,
        summary="Some claims not supported.",
        can_repair=True,
        repaired_answer="Repaired answer.",
    )
    followup = MockFollowup()

    service = SqlAlchemyLectureQAService(
        db=db_session,
        retriever=retriever,
        answerer=answerer,
        verifier=verifier,
        followup=followup,
    )

    response = await service.ask(
        session_id="session_123",
        user_id="user_1",
        question="What is this?",
        lang_mode="ja",
        retrieval_mode="source-only",
        top_k=5,
        context_window=1,
    )

    # Should use repaired answer
    assert response.answer == "Repaired answer."
    assert response.confidence == "medium"  # Downgraded after repair
    assert len(verifier.verify_calls) == 2  # Original + re-verify
    assert len(verifier.repair_calls) == 1


@pytest.mark.asyncio
async def test_ask_with_verification_failure_no_repair_returns_fallback(
    db_session: AsyncSession,
) -> None:
    """Service should return fallback when verification fails and repair fails."""
    await _seed_lecture_session(db_session)
    sources = [
        LectureSource(
            chunk_id="speech_1",
            type="speech",
            text="Test content",
            bm25_score=5.0,
        )
    ]
    retriever = MockRetriever(sources)
    original_answer = "Original unsupported answer."
    answerer = MockAnswerer(
        LectureAnswerDraft(
            answer=original_answer,
            confidence="high",
            action_next="Action.",
        )
    )
    # Verification fails and repair fails
    verifier = MockVerifier(
        passed=False,
        summary="Claims not supported.",
        can_repair=False,
    )
    followup = MockFollowup()

    service = SqlAlchemyLectureQAService(
        db=db_session,
        retriever=retriever,
        answerer=answerer,
        verifier=verifier,
        followup=followup,
    )

    response = await service.ask(
        session_id="session_123",
        user_id="user_1",
        question="What is this?",
        lang_mode="ja",
        retrieval_mode="source-only",
        top_k=5,
        context_window=1,
    )

    # Should return fallback with original answer
    assert response.answer == original_answer
    assert response.fallback == original_answer
    assert response.verification_summary == "Claims not supported."
    assert len(verifier.verify_calls) == 1
    assert len(verifier.repair_calls) == 1


@pytest.mark.asyncio
async def test_followup_with_sources_resolves_query_and_returns_answer(
    db_session: AsyncSession,
) -> None:
    """Service should resolve follow-up query and return answer."""
    await _seed_lecture_session(db_session)
    sources = [
        LectureSource(
            chunk_id="speech_1",
            type="speech",
            text="Test content",
            bm25_score=5.0,
        )
    ]
    retriever = MockRetriever(sources)
    answerer = MockAnswerer(
        LectureAnswerDraft(
            answer="Contextual answer.",
            confidence="high",
            action_next="Action.",
        )
    )
    verifier = MockVerifier(passed=True, summary="Verified.")
    followup = MockFollowup(
        standalone_query="What is machine learning?",
        history_context="Previous context.",
    )

    service = SqlAlchemyLectureQAService(
        db=db_session,
        retriever=retriever,
        answerer=answerer,
        verifier=verifier,
        followup=followup,
    )

    response = await service.followup(
        session_id="session_123",
        user_id="user_1",
        question="What about that?",
        lang_mode="ja",
        retrieval_mode="source-only",
        top_k=5,
        context_window=1,
        history_turns=3,
    )

    assert response.answer == "Contextual answer."
    assert response.resolved_query == "What is machine learning?"
    assert len(followup.resolve_calls) == 1
    assert followup.resolve_calls[0]["question"] == "What about that?"

    # Verify retriever was called with resolved query
    assert retriever.retrieve_calls[0]["query"] == "What is machine learning?"

    # Verify answerer was called with history context
    assert answerer.answer_calls[0]["history"] == "Previous context."


@pytest.mark.asyncio
async def test_followup_without_sources_returns_fallback(
    db_session: AsyncSession,
) -> None:
    """Service should return fallback when follow-up retrieval finds no sources."""
    await _seed_lecture_session(db_session)
    retriever = MockRetriever([])  # No sources
    answerer = MockAnswerer()
    verifier = MockVerifier()
    followup = MockFollowup()

    service = SqlAlchemyLectureQAService(
        db=db_session,
        retriever=retriever,
        answerer=answerer,
        verifier=verifier,
        followup=followup,
    )

    response = await service.followup(
        session_id="session_123",
        user_id="user_1",
        question="What about that?",
        lang_mode="ja",
        retrieval_mode="source-only",
        top_k=5,
        context_window=1,
        history_turns=3,
    )

    assert response.answer == "講義資料に該当する情報が見つかりませんでした。"
    assert response.confidence == "low"
    assert response.sources == []
    assert response.fallback is not None
    assert len(answerer.answer_calls) == 0


@pytest.mark.asyncio
async def test_ask_respects_retrieval_limit(
    db_session: AsyncSession,
) -> None:
    """Service should respect retrieval_limit when calling retriever."""
    await _seed_lecture_session(db_session)
    sources = [
        LectureSource(
            chunk_id=f"speech_{i}",
            type="speech",
            text=f"Content {i}",
            bm25_score=float(i),
        )
        for i in range(10)
    ]
    retriever = MockRetriever(sources)
    answerer = MockAnswerer()
    verifier = MockVerifier(passed=True)
    followup = MockFollowup()

    service = SqlAlchemyLectureQAService(
        db=db_session,
        retriever=retriever,
        answerer=answerer,
        verifier=verifier,
        followup=followup,
        retrieval_limit=3,  # Limit to 3
    )

    await service.ask(
        session_id="session_123",
        user_id="user_1",
        question="Test?",
        lang_mode="ja",
        retrieval_mode="source-only",
        top_k=10,  # Request more than limit
        context_window=1,
    )

    # Retriever should be called with limited top_k
    assert retriever.retrieve_calls[0]["top_k"] == 3


@pytest.mark.asyncio
async def test_ask_uses_custom_fallback_messages(
    db_session: AsyncSession,
) -> None:
    """Service should use custom fallback messages when configured."""
    await _seed_lecture_session(db_session)
    retriever = MockRetriever([])
    answerer = MockAnswerer()
    verifier = MockVerifier()
    followup = MockFollowup()

    custom_fallback = "カスタムフォールバックメッセージ"
    custom_action = "別の質問をお試しください。"

    service = SqlAlchemyLectureQAService(
        db=db_session,
        retriever=retriever,
        answerer=answerer,
        verifier=verifier,
        followup=followup,
        no_source_fallback=custom_fallback,
        no_source_action_next=custom_action,
    )

    response = await service.ask(
        session_id="session_123",
        user_id="user_1",
        question="Test?",
        lang_mode="ja",
        retrieval_mode="source-only",
        top_k=5,
        context_window=1,
    )

    assert response.answer == custom_fallback
    assert response.action_next == custom_action
    assert response.fallback == custom_fallback


@pytest.mark.asyncio
async def test_ask_unknown_or_other_user_session_raises_not_found(
    db_session: AsyncSession,
) -> None:
    """Service should reject sessions not owned by caller."""
    await _seed_lecture_session(
        db_session,
        session_id="session_other",
        user_id="user_other",
    )
    service = SqlAlchemyLectureQAService(
        db=db_session,
        retriever=MockRetriever([]),
        answerer=MockAnswerer(),
        verifier=MockVerifier(),
        followup=MockFollowup(),
    )

    with pytest.raises(LectureSessionNotFoundError):
        await service.ask(
            session_id="session_other",
            user_id="user_1",
            question="Test?",
            lang_mode="ja",
            retrieval_mode="source-only",
            top_k=5,
            context_window=1,
        )
