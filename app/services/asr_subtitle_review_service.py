"""Subtitle audit review service (generator + judge + retry)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.asr_hallucination_judge_service import (
    HallucinationJudgeResult,
    JapaneseASRHallucinationJudgeService,
)
from app.services.asr_japanese_correction_service import JapaneseASRCorrectionService

__all__ = [
    "SubtitleReviewAttempt",
    "SubtitleReviewResult",
    "SubtitleReviewService",
]


@dataclass(frozen=True)
class SubtitleReviewAttempt:
    """A single review attempt result."""

    attempt_no: int
    review_status: str
    input_text: str
    candidate_text: str | None
    corrected_text: str
    was_corrected: bool
    failure_reason: str | None
    judge_confidence: float | None


@dataclass(frozen=True)
class SubtitleReviewResult:
    """Final review decision for subtitle text."""

    original_text: str
    corrected_text: str
    review_status: str
    was_corrected: bool
    retry_count: int
    failure_reason: str | None
    attempts: list[SubtitleReviewAttempt]


class SubtitleReviewService:
    """Review subtitle text and apply correction only when judge approves."""

    _SAFE_LITERAL_REPLACEMENTS: tuple[tuple[str, str], ...] = (
        ("念", "年"),
    )

    def __init__(
        self,
        *,
        correction_service: JapaneseASRCorrectionService,
        judge_service: JapaneseASRHallucinationJudgeService,
        retry_max: int = 1,
    ) -> None:
        self._correction_service = correction_service
        self._judge_service = judge_service
        self._retry_max = max(0, retry_max)

    async def review(self, text: str) -> SubtitleReviewResult:
        source_text = text.strip()
        attempts: list[SubtitleReviewAttempt] = []
        final_failure_reason: str | None = None

        for attempt_index in range(self._retry_max + 1):
            attempt_no = attempt_index + 1
            try:
                candidate_raw = await self._correction_service.correct_minimally(source_text)
                candidate = candidate_raw.strip() or source_text

                if candidate == source_text:
                    attempts.append(
                        SubtitleReviewAttempt(
                            attempt_no=attempt_no,
                            review_status="reviewed",
                            input_text=source_text,
                            candidate_text=candidate,
                            corrected_text=source_text,
                            was_corrected=False,
                            failure_reason=None,
                            judge_confidence=1.0,
                        )
                    )
                    return SubtitleReviewResult(
                        original_text=source_text,
                        corrected_text=source_text,
                        review_status="reviewed",
                        was_corrected=False,
                        retry_count=attempt_index,
                        failure_reason=None,
                        attempts=attempts,
                    )

                judge: HallucinationJudgeResult = await self._judge_service.judge(
                    original_text=source_text,
                    candidate_text=candidate,
                )
                was_corrected = judge.should_apply
                corrected_text = candidate if was_corrected else source_text
                attempts.append(
                    SubtitleReviewAttempt(
                        attempt_no=attempt_no,
                        review_status="reviewed",
                        input_text=source_text,
                        candidate_text=candidate,
                        corrected_text=corrected_text,
                        was_corrected=was_corrected,
                        failure_reason=None,
                        judge_confidence=judge.confidence,
                    )
                )
                return SubtitleReviewResult(
                    original_text=source_text,
                    corrected_text=corrected_text,
                    review_status="reviewed",
                    was_corrected=was_corrected,
                    retry_count=attempt_index,
                    failure_reason=None,
                    attempts=attempts,
                )
            except Exception as exc:  # noqa: BLE001
                if self._is_safe_local_correction(
                    original_text=source_text,
                    candidate_text=candidate if "candidate" in locals() else source_text,
                ):
                    corrected_text = candidate.strip()
                    attempts.append(
                        SubtitleReviewAttempt(
                            attempt_no=attempt_no,
                            review_status="reviewed",
                            input_text=source_text,
                            candidate_text=corrected_text,
                            corrected_text=corrected_text,
                            was_corrected=True,
                            failure_reason=exc.__class__.__name__,
                            judge_confidence=0.51,
                        )
                    )
                    return SubtitleReviewResult(
                        original_text=source_text,
                        corrected_text=corrected_text,
                        review_status="reviewed",
                        was_corrected=True,
                        retry_count=attempt_index,
                        failure_reason=exc.__class__.__name__,
                        attempts=attempts,
                    )
                final_failure_reason = exc.__class__.__name__
                attempts.append(
                    SubtitleReviewAttempt(
                        attempt_no=attempt_no,
                        review_status="review_failed",
                        input_text=source_text,
                        candidate_text=None,
                        corrected_text=source_text,
                        was_corrected=False,
                        failure_reason=final_failure_reason,
                        judge_confidence=None,
                    )
                )

        return SubtitleReviewResult(
            original_text=source_text,
            corrected_text=source_text,
            review_status="review_failed",
            was_corrected=False,
            retry_count=self._retry_max,
            failure_reason=final_failure_reason,
            attempts=attempts,
        )

    @classmethod
    def _is_safe_local_correction(
        cls,
        *,
        original_text: str,
        candidate_text: str,
    ) -> bool:
        original = original_text.strip()
        candidate = candidate_text.strip()
        if not original or not candidate or original == candidate:
            return False
        compact_candidate = re.sub(r"\s+", "", candidate)
        for before, after in cls._SAFE_LITERAL_REPLACEMENTS:
            transformed = original.replace(before, after)
            if transformed == candidate:
                return True
            if re.sub(r"\s+", "", transformed) == compact_candidate:
                return True
        return bool(
            re.fullmatch(
                r"([0-9０-９]{2,4})\s*念.*",
                original,
            )
            and candidate == re.sub(r"([0-9０-９]{2,4})\s*念", r"\1年", original)
        )
