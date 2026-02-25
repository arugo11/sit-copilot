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
from app.services.lecture_answerer_service import (
    LectureAnswerDraft,
    LectureAnswererError,
)
from app.services.lecture_followup_service import FollowupResolution
from app.services.lecture_live_service import LectureSessionNotFoundError
from app.services.lecture_qa_service import SqlAlchemyLectureQAService
from app.services.lecture_verifier_service import (
    LectureVerificationResult,
    LectureVerifierError,
)


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


class ErrorAnswerer:
    """Answerer that always raises LectureAnswererError."""

    async def answer(
        self,
        question: str,
        lang_mode: str,
        sources: list[LectureSource],
        history: str,
    ) -> LectureAnswerDraft:
        _ = (question, lang_mode, sources, history)
        raise LectureAnswererError("Azure OpenAI generation failed")


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
        if self._can_repair and self._repaired_answer and answer == self._repaired_answer:
            return LectureVerificationResult(
                passed=True,
                summary="Re-verified.",
                unsupported_claims=[],
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


class ErrorVerifier:
    """Verifier that always raises LectureVerifierError."""

    def __init__(self) -> None:
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
        raise LectureVerifierError("Azure OpenAI verification failed")

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
        return None


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
    assert qa_turn.outcome_reason == "verified"


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
    assert qa_turn.outcome_reason == "no_source"


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

    await db_session.flush()
    result = await db_session.execute(
        select(QATurn).where(
            QATurn.session_id == "session_123",
            QATurn.question == "What is this?",
        )
    )
    qa_turn = result.scalar_one_or_none()
    assert qa_turn is not None
    assert qa_turn.outcome_reason == "repaired_verified"


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

    await db_session.flush()
    result = await db_session.execute(
        select(QATurn).where(
            QATurn.session_id == "session_123",
            QATurn.question == "What is this?",
        )
    )
    qa_turn = result.scalar_one_or_none()
    assert qa_turn is not None
    assert qa_turn.outcome_reason == "verification_failed"


@pytest.mark.asyncio
async def test_ask_with_answerer_error_returns_local_grounded_answer_and_persists(
    db_session: AsyncSession,
) -> None:
    """Service should return grounded fallback when answerer fails and sources exist."""
    await _seed_lecture_session(db_session)
    sources = [
        LectureSource(
            chunk_id="speech_1",
            type="speech",
            text="Test content from lecture",
            bm25_score=5.0,
        )
    ]
    retriever = MockRetriever(sources)
    answerer = ErrorAnswerer()  # Always raises LectureAnswererError
    verifier = MockVerifier(passed=True, summary="Verified.")
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

    # Should return grounded snippet from sources
    assert response.confidence == "low"
    assert response.answer == "According to ID S-001, Test content from lecture."
    assert response.fallback == "According to ID S-001, Test content from lecture."
    assert (
        response.verification_summary
        == "Answer generation failed, so a grounded snippet from lecture sources was returned."
    )
    assert response.sources == sources

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
    assert qa_turn.citations_json == [sources[0].model_dump()]
    assert qa_turn.retrieved_chunk_ids_json == ["speech_1"]
    assert qa_turn.outcome_reason == "answerer_error_grounded"


@pytest.mark.asyncio
async def test_ask_with_verifier_error_skips_verification_and_persists(
    db_session: AsyncSession,
) -> None:
    """Service should skip verification when verifier fails and return answer."""
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
            answer="Generated answer.",
            confidence="high",
            action_next="Action.",
        )
    )
    verifier = ErrorVerifier()  # Always raises LectureVerifierError
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

    # Should return generated answer even though verification failed
    assert response.answer == "Generated answer."
    assert response.confidence == "high"
    assert response.sources == sources
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
    assert qa_turn.answer == "Generated answer."
    assert qa_turn.citations_json == [sources[0].model_dump()]
    assert qa_turn.retrieved_chunk_ids_json == ["speech_1"]
    assert qa_turn.outcome_reason == "verification_failed"


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
async def test_ask_with_english_question_overrides_lang_mode_to_en(
    db_session: AsyncSession,
) -> None:
    """English question should force lang_mode=en for answer generation."""
    await _seed_lecture_session(db_session)
    sources = [
        LectureSource(
            chunk_id="speech_1",
            type="speech",
            text="Transformer was published in 2017.",
            bm25_score=5.0,
        )
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
    )

    await service.ask(
        session_id="session_123",
        user_id="user_1",
        question="Who developed transformer?",
        lang_mode="ja",
        retrieval_mode="source-only",
        top_k=5,
        context_window=1,
    )

    assert answerer.answer_calls[0]["lang_mode"] == "en"


@pytest.mark.asyncio
async def test_followup_with_english_question_overrides_lang_mode_to_en(
    db_session: AsyncSession,
) -> None:
    """English follow-up should force lang_mode=en even if rewritten query differs."""
    await _seed_lecture_session(db_session)
    sources = [
        LectureSource(
            chunk_id="speech_1",
            type="speech",
            text="Transformer was published in 2017.",
            bm25_score=5.0,
        )
    ]
    retriever = MockRetriever(sources)
    answerer = MockAnswerer()
    verifier = MockVerifier(passed=True)
    followup = MockFollowup(
        standalone_query="Transformerは誰が開発しましたか？",
        history_context="Previous context.",
    )

    service = SqlAlchemyLectureQAService(
        db=db_session,
        retriever=retriever,
        answerer=answerer,
        verifier=verifier,
        followup=followup,
    )

    await service.followup(
        session_id="session_123",
        user_id="user_1",
        question="Who developed transformer?",
        lang_mode="ja",
        retrieval_mode="source-only",
        top_k=5,
        context_window=1,
        history_turns=3,
    )

    assert answerer.answer_calls[0]["lang_mode"] == "en"


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

    await db_session.flush()
    result = await db_session.execute(
        select(QATurn).where(
            QATurn.session_id == "session_123",
            QATurn.question == "What about that?",
        )
    )
    qa_turn = result.scalar_one_or_none()
    assert qa_turn is not None
    assert qa_turn.outcome_reason == "no_source"


@pytest.mark.asyncio
async def test_followup_with_answerer_error_returns_local_grounded_answer(
    db_session: AsyncSession,
) -> None:
    """Service should return grounded snippet when follow-up answerer fails."""
    await _seed_lecture_session(db_session)
    sources = [
        LectureSource(
            chunk_id="speech_1",
            type="speech",
            text="Followup content from lecture",
            bm25_score=5.0,
        )
    ]
    retriever = MockRetriever(sources)
    answerer = ErrorAnswerer()  # Always raises LectureAnswererError
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

    # Should return grounded snippet from sources
    assert response.confidence == "low"
    assert response.answer == "According to ID S-001, Followup content from lecture."
    assert response.fallback == "According to ID S-001, Followup content from lecture."
    assert response.sources == sources
    assert response.resolved_query == "What is machine learning?"

    await db_session.flush()
    result = await db_session.execute(
        select(QATurn).where(
            QATurn.session_id == "session_123",
            QATurn.question == "What about that?",
        )
    )
    qa_turn = result.scalar_one_or_none()
    assert qa_turn is not None
    assert qa_turn.outcome_reason == "answerer_error_grounded"


@pytest.mark.asyncio
async def test_followup_with_verifier_error_skips_verification(
    db_session: AsyncSession,
) -> None:
    """Service should skip verification when follow-up verifier fails."""
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
            answer="Followup answer.",
            confidence="high",
            action_next="Action.",
        )
    )
    verifier = ErrorVerifier()  # Always raises LectureVerifierError
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

    # Should return generated answer even though verification failed
    assert response.answer == "Followup answer."
    assert response.confidence == "high"
    assert response.sources == sources
    assert len(verifier.verify_calls) == 1


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
async def test_ask_keeps_requested_retrieval_mode_and_context_window(
    db_session: AsyncSession,
) -> None:
    """Service should keep caller retrieval mode/context when classifier path is disabled."""
    await _seed_lecture_session(db_session)
    sources = [
        LectureSource(
            chunk_id=f"speech_{i}",
            type="speech",
            text=f"Transformer was announced in 2017 source {i}",
            bm25_score=float(10 - i),
            is_direct_hit=i < 2,
        )
        for i in range(4)
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
        retrieval_limit=10,
        citation_limit=2,
    )

    response = await service.ask(
        session_id="session_123",
        user_id="user_1",
        question="Transformer was developed when?",
        lang_mode="ja",
        retrieval_mode="source-plus-context",
        top_k=8,
        context_window=3,
    )

    assert retriever.retrieve_calls[0]["mode"] == "source-plus-context"
    assert retriever.retrieve_calls[0]["context_window"] == 3
    assert retriever.retrieve_calls[0]["top_k"] == 8
    assert len(response.sources) == 2


@pytest.mark.asyncio
async def test_ask_limits_citations_to_configured_limit(
    db_session: AsyncSession,
) -> None:
    """Service should cap citations and persisted chunk ids by citation_limit."""
    await _seed_lecture_session(db_session)
    sources = [
        LectureSource(
            chunk_id=f"speech_{i}",
            type="speech",
            text=f"Source text {i}",
            bm25_score=float(100 - i),
        )
        for i in range(5)
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
        citation_limit=2,
    )

    response = await service.ask(
        session_id="session_123",
        user_id="user_1",
        question="機械学習とは何ですか",
        lang_mode="ja",
        retrieval_mode="source-only",
        top_k=5,
        context_window=1,
    )

    assert len(response.sources) == 2

    await db_session.flush()
    result = await db_session.execute(
        select(QATurn).where(
            QATurn.session_id == "session_123",
            QATurn.feature == "lecture_qa",
        )
    )
    qa_turn = result.scalar_one_or_none()
    assert qa_turn is not None
    assert len(qa_turn.citations_json) == 2
    assert len(qa_turn.retrieved_chunk_ids_json) == 2


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


@pytest.mark.asyncio
async def test_ask_with_answerer_error_and_empty_sources_includes_failure_reason(
    db_session: AsyncSession,
) -> None:
    """Failure fallback should include raw reason when no grounded snippet can be built."""
    await _seed_lecture_session(db_session)
    # Sources with empty text (will be filtered out)
    sources = [
        LectureSource(
            chunk_id="speech_1",
            type="speech",
            text="   ",  # Only whitespace
            bm25_score=5.0,
        )
    ]
    retriever = MockRetriever(sources)
    answerer = ErrorAnswerer()
    verifier = MockVerifier(passed=True)
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

    # Empty evidence should return explicit failure text with reason
    assert response.confidence == "low"
    assert (
        response.answer
        == "Failed to generate answer. (Reason: Azure OpenAI generation failed)"
    )
    assert response.fallback == response.answer
    assert response.verification_summary == response.answer

    await db_session.flush()
    result = await db_session.execute(
        select(QATurn).where(
            QATurn.session_id == "session_123",
            QATurn.question == "What is this?",
        )
    )
    qa_turn = result.scalar_one_or_none()
    assert qa_turn is not None
    assert qa_turn.outcome_reason == "answerer_error_failure"


@pytest.mark.asyncio
async def test_ask_with_answerer_error_and_single_source_returns_single_snippet(
    db_session: AsyncSession,
) -> None:
    """Service should return grounded snippet when one valid source exists."""
    await _seed_lecture_session(db_session)
    sources = [
        LectureSource(
            chunk_id="speech_1",
            type="speech",
            text="Single source content here",
            bm25_score=5.0,
        )
    ]
    retriever = MockRetriever(sources)
    answerer = ErrorAnswerer()
    verifier = MockVerifier(passed=True)
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

    # Should return grounded snippet from the single source
    assert response.confidence == "low"
    assert response.answer == "According to ID S-001, Single source content here."
    assert response.fallback == "According to ID S-001, Single source content here."


@pytest.mark.asyncio
async def test_ask_with_answerer_error_returns_japanese_failure_message(
    db_session: AsyncSession,
) -> None:
    """Japanese failure message should include raw reason when snippet cannot be built."""
    await _seed_lecture_session(db_session)
    sources = [
        LectureSource(
            chunk_id="speech_1",
            type="speech",
            text="   ",
            bm25_score=5.0,
        )
    ]
    retriever = MockRetriever(sources)
    answerer = ErrorAnswerer()
    verifier = MockVerifier(passed=True)
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
        question="トランスフォーマーの特徴は？",
        lang_mode="ja",
        retrieval_mode="source-only",
        top_k=5,
        context_window=1,
    )

    assert (
        response.answer
        == "回答文生成に失敗しました。（理由: Azure OpenAI generation failed）"
    )
    assert response.fallback == response.answer


@pytest.mark.asyncio
async def test_ask_with_answerer_error_uses_top_ranked_source_for_grounded_fallback(
    db_session: AsyncSession,
) -> None:
    """Grounded fallback should use top-ranked citation source when answerer fails."""
    await _seed_lecture_session(db_session)
    sources = [
        LectureSource(
            chunk_id="S-001",
            type="speech",
            text="トランスフォーマーは2017年6月12日に Google の研究者等が発表した モデル",
            bm25_score=9.0,
            is_direct_hit=True,
        ),
        LectureSource(
            chunk_id="S-002",
            type="speech",
            text="逐次処理が不要という特徴がある",
            bm25_score=8.0,
            is_direct_hit=True,
        ),
    ]
    retriever = MockRetriever(sources)
    answerer = ErrorAnswerer()
    verifier = MockVerifier(passed=True)
    followup = MockFollowup()

    service = SqlAlchemyLectureQAService(
        db=db_session,
        retriever=retriever,
        answerer=answerer,
        verifier=verifier,
        followup=followup,
        citation_limit=1,
    )

    response = await service.ask(
        session_id="session_123",
        user_id="user_1",
        question="Transformerはいつ開発された?",
        lang_mode="ja",
        retrieval_mode="source-only",
        top_k=5,
        context_window=1,
    )

    assert response.answer.startswith("ID S-001によると、")
    assert response.fallback == response.answer
    assert len(response.sources) == 1
    assert response.sources[0].chunk_id == "S-001"


@pytest.mark.asyncio
async def test_followup_with_answerer_error_includes_resolved_query(
    db_session: AsyncSession,
) -> None:
    """Service should include resolved_query in followup error response."""
    await _seed_lecture_session(db_session)
    sources = [
        LectureSource(
            chunk_id="speech_1",
            type="speech",
            text="Content here",
            bm25_score=5.0,
        )
    ]
    retriever = MockRetriever(sources)
    answerer = ErrorAnswerer()
    verifier = MockVerifier(passed=True)
    followup = MockFollowup(
        standalone_query="Resolved standalone query",
        history_context="Context",
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
        question="Followup question?",
        lang_mode="ja",
        retrieval_mode="source-only",
        top_k=5,
        context_window=1,
        history_turns=3,
    )

    # Should include resolved_query in error response
    assert response.resolved_query == "Resolved standalone query"
    assert response.confidence == "low"


@pytest.mark.asyncio
async def test_ask_with_verification_failure_and_repair_error_safely_continues(
    db_session: AsyncSession,
) -> None:
    """Service should continue safely when both verification and repair fail."""
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
    # Verification fails, and repair also fails (returns None)
    verifier = MockVerifier(
        passed=False,
        summary="Claims not supported.",
        can_repair=False,  # Repair fails
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

    # Should return original answer with fallback
    assert response.answer == "Original answer."
    assert response.fallback == "Original answer."
    assert len(verifier.verify_calls) == 1
    assert len(verifier.repair_calls) == 1


@pytest.mark.asyncio
async def test_followup_with_verifier_repair_error_continues_safely(
    db_session: AsyncSession,
) -> None:
    """Service should continue safely when followup verifier repair fails."""
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
            answer="Followup answer.",
            confidence="high",
            action_next="Action.",
        )
    )
    # Use ErrorVerifier which raises on repair
    verifier = ErrorVerifier()
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
        question="Followup?",
        lang_mode="ja",
        retrieval_mode="source-only",
        top_k=5,
        context_window=1,
        history_turns=3,
    )

    # Should return answer despite verification/repair errors
    assert response.answer == "Followup answer."
    assert response.confidence == "high"
    assert len(verifier.verify_calls) == 1
