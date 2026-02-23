"""Judge service for deciding whether ASR subtitle correction should be applied."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.core.azure_openai_config import ValidationResult, validate_openai_config
from app.services.observability.llm_usage import LLMUsage, extract_usage

__all__ = [
    "HallucinationJudgeResult",
    "JapaneseASRHallucinationJudgeService",
    "AzureOpenAIJapaneseASRHallucinationJudgeService",
    "NoopJapaneseASRHallucinationJudgeService",
]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HallucinationJudgeResult:
    """Decision from hallucination judge."""

    should_apply: bool
    confidence: float
    reason: str


class JapaneseASRHallucinationJudgeService(Protocol):
    """Interface for judging whether correction should be applied."""

    async def judge(
        self,
        *,
        original_text: str,
        candidate_text: str,
    ) -> HallucinationJudgeResult:
        """Return judge decision for correction application."""
        ...


class NoopJapaneseASRHallucinationJudgeService:
    """Fallback judge that applies changed text when correction differs."""

    def __init__(
        self,
        *,
        warning_reason: str | None = None,
    ) -> None:
        self._warning_reason = warning_reason
        self._warning_emitted = False

    async def judge(
        self,
        *,
        original_text: str,
        candidate_text: str,
    ) -> HallucinationJudgeResult:
        if self._warning_reason and not self._warning_emitted:
            self._warning_emitted = True
            logger.warning(self._warning_reason)
        changed = candidate_text.strip() != original_text.strip()
        return HallucinationJudgeResult(
            should_apply=changed,
            confidence=1.0 if changed else 0.0,
            reason="noop_fallback",
        )


class AzureOpenAIJapaneseASRHallucinationJudgeService:
    """Azure OpenAI-backed judge for strict hallucination gating."""

    DEFAULT_API_VERSION = "2024-10-21"

    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str,
        account_name: str = "",
        model: str,
        api_version: str = DEFAULT_API_VERSION,
        timeout_seconds: int = 20,
        obvious_threshold: float = 0.85,
    ) -> None:
        self._api_key = api_key
        self._endpoint = endpoint
        self._account_name = account_name
        self._model = model
        self._api_version = api_version
        self._timeout_seconds = timeout_seconds
        self._obvious_threshold = obvious_threshold
        self._last_usage: LLMUsage | None = None
        self._validation = self._validate_configuration()

        if not self._validation.is_valid:
            logger.info(
                "azure_openai_asr_judge_config_invalid reason=%s",
                self._validation.reason,
            )

    async def judge(
        self,
        *,
        original_text: str,
        candidate_text: str,
    ) -> HallucinationJudgeResult:
        if original_text.strip() == candidate_text.strip():
            return HallucinationJudgeResult(
                should_apply=False,
                confidence=1.0,
                reason="identical_text",
            )

        if not self._validation.is_valid:
            return HallucinationJudgeResult(
                should_apply=False,
                confidence=0.0,
                reason=f"judge_unavailable:{self._validation.reason}",
            )

        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a strict Japanese subtitle correction judge. "
                        "Approve corrections only when original text has an obvious ASR hallucination "
                        "and candidate fixes it without changing intent."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "次の原文と候補を比較し、候補を適用すべきかを厳格に判定してください。\n"
                        "判定基準:\n"
                        "- 明らかな誤認識/破綻が原文にある\n"
                        "- 候補が意味を変えずに修正している\n"
                        "- グレーなら不採用\n"
                        "JSONのみで返答:\n"
                        "{\"is_obvious_hallucination\": bool, \"confidence\": 0..1, \"reason\": string}\n\n"
                        f"original:\n{original_text}\n\n"
                        f"candidate:\n{candidate_text}"
                    ),
                },
            ],
            "max_completion_tokens": 220,
            "response_format": {"type": "json_object"},
        }

        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url=self._build_chat_completion_url(),
            data=body,
            headers={
                "Content-Type": "application/json",
                "api-key": self._api_key,
            },
            method="POST",
        )

        def _run_request() -> str:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                return response.read().decode("utf-8")

        try:
            raw = await asyncio.to_thread(_run_request)
            response_json = json.loads(raw)
            self._last_usage = extract_usage(response_json)
            content = self._extract_content(response_json)
            parsed = json.loads(content)

            confidence_raw = parsed.get("confidence", 0.0)
            confidence = (
                float(confidence_raw)
                if isinstance(confidence_raw, int | float)
                else 0.0
            )
            confidence = max(0.0, min(1.0, confidence))

            obvious = bool(parsed.get("is_obvious_hallucination", False))
            reason_raw = parsed.get("reason", "")
            reason = reason_raw.strip() if isinstance(reason_raw, str) else ""

            should_apply = obvious and confidence >= self._obvious_threshold
            return HallucinationJudgeResult(
                should_apply=should_apply,
                confidence=confidence,
                reason=reason or "judge_ok",
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("asr judge failed") from exc

    def _build_chat_completion_url(self) -> str:
        endpoint = self._validation.normalized_endpoint.rstrip("/")
        deployment = quote(self._model.strip(), safe="")
        return (
            f"{endpoint}/openai/deployments/{deployment}/chat/completions"
            f"?api-version={self._api_version}"
        )

    def _validate_configuration(self) -> ValidationResult:
        return validate_openai_config(
            api_key=self._api_key,
            endpoint=self._endpoint,
            deployment=self._model,
            account_name=self._account_name,
        )

    def _extract_content(self, response_json: dict[str, object]) -> str:
        choices = response_json.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("missing choices")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ValueError("invalid first choice")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ValueError("missing message")

        content = message.get("content")
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            text_parts: list[str] = []
            for part in content:
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    text_parts.append(text.strip())
            if text_parts:
                return "\n".join(text_parts)

        raise ValueError("missing content")
