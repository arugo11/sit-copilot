"""Unit tests for lecture QA schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.lecture_qa import (
    LangMode,
    LectureAskRequest,
    LectureAskResponse,
    LectureCitation,
    LectureFollowupRequest,
    LectureFollowupResponse,
    LectureIndexBuildRequest,
    LectureIndexBuildResponse,
    LectureQAConfidence,
    LectureSource,
    RetrievalMode,
)


class TestLectureSource:
    """Tests for LectureSource schema."""

    def test_valid_speech_source(self) -> None:
        """Valid speech source should be accepted."""
        data = {
            "chunk_id": "speech_123",
            "type": "speech",
            "text": "This is a test transcript.",
            "timestamp": "12:34",
            "start_ms": 754000,
            "end_ms": 756000,
            "speaker": "teacher",
            "bm25_score": 5.2,
            "is_direct_hit": True,
        }
        source = LectureSource(**data)
        assert source.chunk_id == "speech_123"
        assert source.type == "speech"
        assert source.text == "This is a test transcript."
        assert source.timestamp == "12:34"
        assert source.bm25_score == 5.2
        assert source.is_direct_hit is True

    def test_valid_visual_source(self) -> None:
        """Valid visual source should be accepted."""
        data = {
            "chunk_id": "visual_456",
            "type": "visual",
            "text": "Slide content about machine learning.",
            "bm25_score": 3.1,
            "is_direct_hit": False,
        }
        source = LectureSource(**data)
        assert source.chunk_id == "visual_456"
        assert source.type == "visual"
        assert source.is_direct_hit is False

    def test_extra_fields_forbidden(self) -> None:
        """Extra fields should raise ValidationError."""
        data = {
            "chunk_id": "speech_123",
            "type": "speech",
            "text": "Test",
            "bm25_score": 1.0,
            "unexpected_field": "value",
        }
        with pytest.raises(ValidationError):
            LectureSource(**data)


class TestLectureCitation:
    """Tests for LectureCitation schema."""

    def test_valid_citation(self) -> None:
        """Valid citation should be accepted."""
        data = {
            "chunk_id": "speech_123",
            "type": "speech",
            "timestamp": "12:34",
            "text": "This is a snippet.",
        }
        citation = LectureCitation(**data)
        assert citation.chunk_id == "speech_123"
        assert citation.type == "speech"
        assert citation.text == "This is a snippet."

    def test_citation_without_timestamp(self) -> None:
        """Citation without timestamp should be accepted."""
        data = {
            "chunk_id": "visual_456",
            "type": "visual",
            "text": "Visual content snippet.",
        }
        citation = LectureCitation(**data)
        assert citation.timestamp is None


class TestLectureAskRequest:
    """Tests for LectureAskRequest schema."""

    def test_valid_minimal_request(self) -> None:
        """Valid minimal request with defaults should be accepted."""
        data = {
            "session_id": "session_123",
            "question": "What is machine learning?",
        }
        req = LectureAskRequest(**data)
        assert req.session_id == "session_123"
        assert req.question == "What is machine learning?"
        assert req.lang_mode == "ja"
        assert req.retrieval_mode == "source-only"
        assert req.top_k == 5
        assert req.context_window == 1

    def test_valid_full_request(self) -> None:
        """Valid full request with all fields should be accepted."""
        data = {
            "session_id": "session_123",
            "question": "What is machine learning?",
            "lang_mode": "easy-ja",
            "retrieval_mode": "source-plus-context",
            "top_k": 10,
            "context_window": 2,
        }
        req = LectureAskRequest(**data)
        assert req.lang_mode == "easy-ja"
        assert req.retrieval_mode == "source-plus-context"
        assert req.top_k == 10
        assert req.context_window == 2

    def test_session_id_normalization(self) -> None:
        """Session ID should be normalized (whitespace trimmed)."""
        req = LectureAskRequest(session_id="  session_123  ", question="Test question?")
        assert req.session_id == "session_123"

    def test_session_id_blank_raises_error(self) -> None:
        """Blank session ID should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LectureAskRequest(session_id="   ", question="Test question?")
        assert "session_id must not be blank" in str(exc_info.value)

    def test_question_normalization(self) -> None:
        """Question should be normalized (whitespace trimmed)."""
        req = LectureAskRequest(session_id="session_123", question="  What is this?  ")
        assert req.question == "What is this?"

    def test_question_blank_raises_error(self) -> None:
        """Blank question should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LectureAskRequest(session_id="session_123", question="   ")
        assert "question must not be blank" in str(exc_info.value)

    def test_invalid_lang_mode_raises_error(self) -> None:
        """Invalid lang_mode should raise ValidationError."""
        with pytest.raises(ValidationError):
            LectureAskRequest(
                session_id="session_123",
                question="Test?",
                lang_mode="fr",  # Invalid
            )

    def test_invalid_retrieval_mode_raises_error(self) -> None:
        """Invalid retrieval_mode should raise ValidationError."""
        with pytest.raises(ValidationError):
            LectureAskRequest(
                session_id="session_123",
                question="Test?",
                retrieval_mode="hybrid",  # Invalid
            )

    def test_top_k_below_minimum_raises_error(self) -> None:
        """top_k below minimum should raise ValidationError."""
        with pytest.raises(ValidationError):
            LectureAskRequest(session_id="session_123", question="Test?", top_k=0)

    def test_top_k_above_maximum_raises_error(self) -> None:
        """top_k above maximum should raise ValidationError."""
        with pytest.raises(ValidationError):
            LectureAskRequest(session_id="session_123", question="Test?", top_k=25)

    def test_context_window_below_minimum_raises_error(self) -> None:
        """context_window below minimum should raise ValidationError."""
        with pytest.raises(ValidationError):
            LectureAskRequest(
                session_id="session_123", question="Test?", context_window=-1
            )

    def test_context_window_above_maximum_raises_error(self) -> None:
        """context_window above maximum should raise ValidationError."""
        with pytest.raises(ValidationError):
            LectureAskRequest(
                session_id="session_123", question="Test?", context_window=10
            )

    def test_missing_session_id_raises_error(self) -> None:
        """Missing session_id should raise ValidationError."""
        with pytest.raises(ValidationError):
            LectureAskRequest(question="Test?")

    def test_missing_question_raises_error(self) -> None:
        """Missing question should raise ValidationError."""
        with pytest.raises(ValidationError):
            LectureAskRequest(session_id="session_123")


class TestLectureAskResponse:
    """Tests for LectureAskResponse schema."""

    def test_valid_response_with_sources(self) -> None:
        """Valid response with sources should be accepted."""
        data = {
            "answer": "Machine learning is a subset of AI.",
            "confidence": "high",
            "sources": [
                {
                    "chunk_id": "speech_1",
                    "type": "speech",
                    "text": "ML is a subset of AI",
                    "bm25_score": 5.0,
                }
            ],
            "verification_summary": "All claims verified.",
            "action_next": "Ask more questions.",
        }
        resp = LectureAskResponse(**data)
        assert resp.answer == "Machine learning is a subset of AI."
        assert resp.confidence == "high"
        assert len(resp.sources) == 1
        assert resp.fallback is None

    def test_valid_fallback_response(self) -> None:
        """Valid fallback response should be accepted."""
        data = {
            "answer": "I couldn't find relevant information.",
            "confidence": "low",
            "sources": [],
            "action_next": "Try rephrasing your question.",
            "fallback": "No relevant sources found in the lecture.",
        }
        resp = LectureAskResponse(**data)
        assert resp.confidence == "low"
        assert resp.sources == []
        assert resp.fallback is not None
        assert resp.verification_summary is None

    def test_invalid_confidence_raises_error(self) -> None:
        """Invalid confidence should raise ValidationError."""
        data = {
            "answer": "Test answer.",
            "confidence": "very_high",  # Invalid
            "sources": [],
            "action_next": "Next.",
        }
        with pytest.raises(ValidationError):
            LectureAskResponse(**data)


class TestLectureFollowupRequest:
    """Tests for LectureFollowupRequest schema."""

    def test_valid_minimal_request(self) -> None:
        """Valid minimal request with defaults should be accepted."""
        data = {
            "session_id": "session_123",
            "question": "What about that?",
        }
        req = LectureFollowupRequest(**data)
        assert req.session_id == "session_123"
        assert req.question == "What about that?"
        assert req.history_turns == 3

    def test_valid_full_request(self) -> None:
        """Valid full request with all fields should be accepted."""
        data = {
            "session_id": "session_123",
            "question": "What about that?",
            "lang_mode": "en",
            "retrieval_mode": "source-plus-context",
            "top_k": 8,
            "context_window": 2,
            "history_turns": 5,
        }
        req = LectureFollowupRequest(**data)
        assert req.lang_mode == "en"
        assert req.history_turns == 5

    def test_history_turns_below_minimum_raises_error(self) -> None:
        """history_turns below minimum should raise ValidationError."""
        with pytest.raises(ValidationError):
            LectureFollowupRequest(
                session_id="session_123", question="Test?", history_turns=0
            )

    def test_history_turns_above_maximum_raises_error(self) -> None:
        """history_turns above maximum should raise ValidationError."""
        with pytest.raises(ValidationError):
            LectureFollowupRequest(
                session_id="session_123", question="Test?", history_turns=15
            )


class TestLectureFollowupResponse:
    """Tests for LectureFollowupResponse schema."""

    def test_valid_response(self) -> None:
        """Valid followup response should be accepted."""
        data = {
            "answer": "Based on context, that refers to...",
            "confidence": "medium",
            "sources": [],
            "action_next": "Continue.",
            "resolved_query": "What is machine learning?",
        }
        resp = LectureFollowupResponse(**data)
        assert resp.resolved_query == "What is machine learning?"


class TestLectureIndexBuildRequest:
    """Tests for LectureIndexBuildRequest schema."""

    def test_valid_request(self) -> None:
        """Valid request should be accepted."""
        data = {
            "session_id": "session_123",
            "rebuild": False,
        }
        req = LectureIndexBuildRequest(**data)
        assert req.session_id == "session_123"
        assert req.rebuild is False

    def test_valid_minimal_request(self) -> None:
        """Valid minimal request with defaults should be accepted."""
        req = LectureIndexBuildRequest(session_id="session_123")
        assert req.rebuild is False

    def test_session_id_normalization(self) -> None:
        """Session ID should be normalized."""
        req = LectureIndexBuildRequest(session_id="  session_123  ")
        assert req.session_id == "session_123"

    def test_session_id_blank_raises_error(self) -> None:
        """Blank session ID should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LectureIndexBuildRequest(session_id="   ")
        assert "session_id must not be blank" in str(exc_info.value)


class TestLectureIndexBuildResponse:
    """Tests for LectureIndexBuildResponse schema."""

    def test_valid_success_response(self) -> None:
        """Valid success response should be accepted."""
        from datetime import UTC, datetime

        data = {
            "index_version": "v1",
            "chunk_count": 150,
            "built_at": datetime.now(UTC),
            "status": "success",
        }
        resp = LectureIndexBuildResponse(**data)
        assert resp.status == "success"
        assert resp.chunk_count == 150

    def test_valid_skipped_response(self) -> None:
        """Valid skipped response should be accepted."""
        from datetime import UTC, datetime

        data = {
            "index_version": "v1",
            "chunk_count": 150,
            "built_at": datetime.now(UTC),
            "status": "skipped",
        }
        resp = LectureIndexBuildResponse(**data)
        assert resp.status == "skipped"

    def test_invalid_status_raises_error(self) -> None:
        """Invalid status should raise ValidationError."""
        from datetime import UTC, datetime

        data = {
            "index_version": "v1",
            "chunk_count": 150,
            "built_at": datetime.now(UTC),
            "status": "pending",  # Invalid
        }
        with pytest.raises(ValidationError):
            LectureIndexBuildResponse(**data)


class TestTypeAliases:
    """Tests for type alias literals."""

    def test_lang_mode_values(self) -> None:
        """LangMode should have correct literal values."""
        valid_modes = ["ja", "easy-ja", "en"]
        for mode in valid_modes:
            assert mode in LangMode.__args__

    def test_lecture_qa_confidence_values(self) -> None:
        """LectureQAConfidence should have correct literal values."""
        valid_confidences = ["high", "medium", "low"]
        for conf in valid_confidences:
            assert conf in LectureQAConfidence.__args__

    def test_retrieval_mode_values(self) -> None:
        """RetrievalMode should have correct literal values."""
        valid_modes = ["source-only", "source-plus-context"]
        for mode in valid_modes:
            assert mode in RetrievalMode.__args__
