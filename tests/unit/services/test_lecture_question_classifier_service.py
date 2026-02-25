"""Unit tests for lecture question classifier service."""

import pytest

from app.services.lecture_question_classifier_service import (
    HeuristicLectureQuestionClassifierService,
)


@pytest.mark.asyncio
async def test_heuristic_classifier_detects_factoid_ja() -> None:
    """Japanese date question should be classified as factoid."""
    service = HeuristicLectureQuestionClassifierService()

    result = await service.classify(
        question="Transformerはいつ開発された?",
        lang_mode="ja",
    )

    assert result.question_type == "factoid"
    assert result.confidence > 0.0


@pytest.mark.asyncio
async def test_heuristic_classifier_detects_factoid_en() -> None:
    """English factual question should be classified as factoid."""
    service = HeuristicLectureQuestionClassifierService()

    result = await service.classify(
        question="When was Transformer developed?",
        lang_mode="ja",
    )

    assert result.question_type == "factoid"
