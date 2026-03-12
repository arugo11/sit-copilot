"""Japanese ASR minimal correction service."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.core.azure_openai_config import ValidationResult, validate_openai_config
from app.services.observability.llm_usage import LLMUsage, extract_usage

__all__ = [
    "JapaneseASRCorrectionService",
    "AzureOpenAIJapaneseASRCorrectionService",
    "NoopJapaneseASRCorrectionService",
]

logger = logging.getLogger(__name__)


class JapaneseASRCorrectionService(Protocol):
    """Interface for minimal correction of Japanese ASR text."""

    async def correct_minimally(self, text: str) -> str:
        """Return minimally corrected Japanese text."""
        ...


class NoopJapaneseASRCorrectionService:
    """Fallback correction service that leaves input text unchanged."""

    _warning_emitted = False

    def __init__(self, *, warning_reason: str | None = None) -> None:
        self._warning_reason = warning_reason

    async def correct_minimally(self, text: str) -> str:
        if self._warning_reason and not NoopJapaneseASRCorrectionService._warning_emitted:
            NoopJapaneseASRCorrectionService._warning_emitted = True
            logger.warning(self._warning_reason)
        return text.strip()


class AzureOpenAIJapaneseASRCorrectionService:
    """Azure OpenAI-backed minimal correction service for Japanese ASR output."""

    DEFAULT_MODEL = "gpt-5-nano"
    DEFAULT_API_VERSION = "2024-05-01-preview"
    DEFAULT_TIMEOUT_SECONDS = 20
    SECOND_PASS_MIN_LENGTH = 40
    _SAFE_REGEX_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
        (re.compile(r"([0-9０-９]{2,4})\s*念"), r"\1年"),
    )

    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str,
        account_name: str = "",
        model: str = DEFAULT_MODEL,
        api_version: str = DEFAULT_API_VERSION,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._endpoint = endpoint
        self._model = model
        self._api_version = api_version
        self._timeout_seconds = timeout_seconds
        self._last_usage: LLMUsage | None = None
        self._validation = self._validate_configuration(account_name=account_name)

        if not self._validation.is_valid:
            logger.info(
                "azure_openai_asr_correction_config_invalid reason=%s",
                self._validation.reason,
            )

    async def correct_minimally(self, text: str) -> str:
        normalized = text.strip()
        if not normalized:
            return ""
        if not self._validation.is_valid:
            return self._apply_local_minimal_fallback(normalized)

        try:
            corrected = await self._call_openai(self._build_prompt(normalized))
            cleaned = corrected.strip()
            if not cleaned:
                return self._apply_local_minimal_fallback(normalized)

            if (
                cleaned == normalized
                and len(normalized) >= self.SECOND_PASS_MIN_LENGTH
            ):
                second_pass = await self._call_openai(
                    self._build_second_pass_prompt(normalized)
                )
                second_cleaned = second_pass.strip()
                if second_cleaned:
                    return second_cleaned

            return self._apply_local_minimal_fallback(cleaned)
        except Exception:  # noqa: BLE001
            logger.warning("asr_minimal_correction_failed", exc_info=True)
            return self._apply_local_minimal_fallback(normalized)

    def _build_prompt(self, text: str) -> str:
        return (
            "あなたは日本語ASRの最小補正アシスタントです。\n"
            "目的: 明らかな認識ミスを最小限に修正し、日本語として破綻した箇所だけを自然に直す。\n"
            "必須ルール:\n"
            "1) 可能な限り原文を維持する。\n"
            "2) 固有名詞・数値・記号は原則そのまま。\n"
            "3) 語尾の好み変更や言い換えはしない。\n"
            "4) 明確な誤りがない場合は原文をそのまま返す。\n"
            "5) 文法的に不自然な連接は必ず修正する（例: 『適し使用される』→『使用される』）。\n"
            "6) 助詞・活用・接続の誤り（例: 『手配を』,『お確認』）は文脈に沿って最小修正する。\n"
            "7) 句読点・括弧・英字略語（例: NLP）は意味を変えずに整える。\n"
            "8) 出力は補正後テキストのみ。説明・注釈は禁止。\n\n"
            f"入力:\n{text}"
        )

    def _build_second_pass_prompt(self, text: str) -> str:
        return (
            "あなたは講義字幕のASR誤認識を修正する校正者です。\n"
            "次の文は音声認識由来で、同音異義語や文脈誤りを含む可能性があります。\n"
            "事実関係は維持しつつ、技術文として自然で文法的に正しい日本語に直してください。\n"
            "必須ルール:\n"
            "1) 意味・主張・時制を変えない。\n"
            "2) 明確な誤認識は積極的に修正する。\n"
            "3) 不必要な言い換えや要約はしない。\n"
            "4) 助詞・活用・連語の破綻を残さない。\n"
            "5) 以下の優先修正を行う: 誤助詞, 活用誤り, 脱落語補完（最小限）, 不自然な語連接。\n"
            "6) 出力は修正後の本文のみ。説明・箇条書きは禁止。\n\n"
            f"入力:\n{text}"
        )

    async def _call_openai(self, prompt: str) -> str:
        url = self._build_chat_completion_url()
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a strict Japanese ASR correction engine. "
                        "Keep meaning unchanged, fix obvious recognition and grammar errors, "
                        "and never leave ungrammatical collocations in the output."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "max_completion_tokens": 600,
        }
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url=url,
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
            return self._extract_content(response_json)
        except HTTPError as exc:
            raise RuntimeError("asr correction http error") from exc
        except URLError as exc:
            raise RuntimeError("asr correction network error") from exc
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("asr correction parse error") from exc

    def _build_chat_completion_url(self) -> str:
        endpoint = self._validation.normalized_endpoint.rstrip("/")
        deployment = quote(self._model.strip(), safe="")
        return (
            f"{endpoint}/openai/deployments/{deployment}/chat/completions"
            f"?api-version={self._api_version}"
        )

    def _validate_configuration(self, *, account_name: str) -> ValidationResult:
        return validate_openai_config(
            api_key=self._api_key,
            endpoint=self._endpoint,
            deployment=self._model,
            account_name=account_name,
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

    def _apply_local_minimal_fallback(self, text: str) -> str:
        corrected = text.strip()
        for pattern, replacement in self._SAFE_REGEX_REPLACEMENTS:
            corrected = pattern.sub(replacement, corrected)
        return corrected
