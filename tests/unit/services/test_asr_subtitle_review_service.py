"""Unit tests for subtitle review fallback behavior."""

import pytest

from app.services.asr_hallucination_judge_service import (
    HallucinationJudgeResult,
)
from app.services.asr_subtitle_review_service import SubtitleReviewService


class _StaticCorrectionService:
    def __init__(self, candidate_text: str) -> None:
        self._candidate_text = candidate_text

    async def correct_minimally(self, text: str) -> str:
        return self._candidate_text


class _FailingJudgeService:
    async def judge(
        self,
        *,
        original_text: str,
        candidate_text: str,
    ) -> HallucinationJudgeResult:
        del original_text, candidate_text
        raise RuntimeError("rate limited")


@pytest.mark.asyncio
async def test_review_applies_safe_local_correction_when_judge_fails() -> None:
    service = SubtitleReviewService(
        correction_service=_StaticCorrectionService(
            "Transformer は 2017年に発表されました。"
        ),
        judge_service=_FailingJudgeService(),
        retry_max=0,
    )

    result = await service.review("Transformer は 2017 念に発表されました。")

    assert result.review_status == "reviewed"
    assert result.was_corrected is True
    assert result.corrected_text == "Transformer は 2017年に発表されました。"
    assert result.failure_reason == "RuntimeError"
