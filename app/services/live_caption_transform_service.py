"""Live subtitle transformation service (English / Easy Japanese)."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.core.azure_openai_config import ValidationResult, validate_openai_config
from app.services.observability.llm_usage import LLMUsage, extract_usage

__all__ = [
    "CaptionTransformResult",
    "CaptionTransformStatus",
    "CaptionTransformService",
    "AzureOpenAILiveCaptionTransformService",
    "UnavailableLiveCaptionTransformService",
]

logger = logging.getLogger(__name__)


CaptionTransformStatus = Literal["translated", "fallback", "passthrough"]


@dataclass(frozen=True, slots=True)
class CaptionTransformResult:
    """Structured transform result with fallback signaling."""

    text: str
    status: CaptionTransformStatus
    fallback_reason: str | None = None


class CaptionTransformLLMError(RuntimeError):
    """Raised when Azure OpenAI transform request fails."""

    def __init__(
        self,
        *,
        reason: str,
        message: str,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.retry_after_seconds = retry_after_seconds


class CaptionTransformService(Protocol):
    """Interface for subtitle language transformation."""

    async def transform(
        self, text: str, target_lang_mode: str
    ) -> CaptionTransformResult:
        """Transform subtitle text according to target language mode."""
        ...


class UnavailableLiveCaptionTransformService:
    """Fail-closed subtitle transform service used when the feature is disabled."""

    def __init__(self, *, reason: str) -> None:
        self._reason = reason

    async def transform(
        self, text: str, target_lang_mode: str
    ) -> CaptionTransformResult:
        normalized_text = text.strip()
        if target_lang_mode == "ja":
            return CaptionTransformResult(
                text=normalized_text,
                status="passthrough",
                fallback_reason=None,
            )
        return CaptionTransformResult(
            text=normalized_text,
            status="fallback",
            fallback_reason=self._reason,
        )


@dataclass(frozen=True, slots=True)
class _PromptSpec:
    system: str
    user: str


class AzureOpenAILiveCaptionTransformService:
    """Azure OpenAI-backed subtitle transformer with safe local fallback."""

    DEFAULT_MODEL = "gpt-5-nano"
    DEFAULT_API_VERSION = "2024-05-01-preview"
    DEFAULT_TIMEOUT_SECONDS = 20
    MAX_RETRY_ATTEMPTS = 2
    RETRY_BASE_DELAY_SECONDS = 0.5
    RETRY_MAX_DELAY_SECONDS = 3.0
    RETRYABLE_ERROR_REASONS = {"llm_rate_limited", "llm_network_error", "llm_http_error"}

    _EN_GLOSSARY: list[tuple[str, str]] = [
        ("機械学習", "machine learning"),
        ("過学習", "overfitting"),
        ("正則化", "regularization"),
        ("検証データ", "validation data"),
        ("訓練データ", "training data"),
        ("未知データ", "unseen data"),
    ]

    _EASY_JA_GLOSSARY: list[tuple[str, str]] = [
        ("機械学習", "AIの学習"),
        ("過学習", "学びすぎ（過学習）"),
        ("正則化", "調整（正則化）"),
        ("検証データ", "チェック用データ"),
        ("訓練データ", "学習用データ"),
        ("未知データ", "はじめてのデータ"),
    ]

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
                "azure_openai_caption_transform_config_invalid reason=%s",
                self._validation.reason,
            )

    async def transform(
        self, text: str, target_lang_mode: str
    ) -> CaptionTransformResult:
        """Transform subtitle text for requested mode."""
        normalized_text = text.strip()
        if not normalized_text:
            return CaptionTransformResult(
                text="",
                status="passthrough",
                fallback_reason=None,
            )
        if target_lang_mode == "ja":
            return CaptionTransformResult(
                text=normalized_text,
                status="passthrough",
                fallback_reason=None,
            )

        if target_lang_mode not in {"en", "easy-ja"}:
            return CaptionTransformResult(
                text=normalized_text,
                status="fallback",
                fallback_reason="unsupported_target_lang_mode",
            )

        if not self._validation.is_valid:
            fallback_text = self._apply_local_fallback(
                text=normalized_text,
                target_lang_mode=target_lang_mode,
            )
            return CaptionTransformResult(
                text=fallback_text,
                status="fallback",
                fallback_reason=self._validation.reason,
            )

        prompt = (
            self._build_en_prompt(normalized_text)
            if target_lang_mode == "en"
            else self._build_easy_ja_prompt(normalized_text)
        )
        try:
            transformed = await self._call_openai_with_retry(prompt)
            cleaned = transformed.strip()
            if cleaned:
                return CaptionTransformResult(
                    text=cleaned,
                    status="translated",
                    fallback_reason=None,
                )
            fallback_reason = "llm_empty_response"
        except CaptionTransformLLMError as exc:
            fallback_reason = exc.reason
            logger.warning(
                "caption_transform_failed mode=%s reason=%s",
                target_lang_mode,
                fallback_reason,
                exc_info=True,
            )
        except Exception:  # noqa: BLE001
            fallback_reason = "llm_unknown_error"
            logger.warning(
                "caption_transform_failed mode=%s reason=%s",
                target_lang_mode,
                fallback_reason,
                exc_info=True,
            )

        fallback_text = self._apply_local_fallback(
            text=normalized_text,
            target_lang_mode=target_lang_mode,
        )
        return CaptionTransformResult(
            text=fallback_text,
            status="fallback",
            fallback_reason=fallback_reason,
        )

    def _build_en_prompt(self, text: str) -> _PromptSpec:
        return _PromptSpec(
            system=(
                "You are a live-caption translator for lectures. "
                "Translate Japanese subtitles into natural, concise English."
            ),
            user=(
                "Translate the following Japanese subtitle to English.\n"
                "Rules:\n"
                "1) Preserve facts, numbers, proper nouns, and negation exactly.\n"
                "2) Keep lecture meaning and technical intent.\n"
                "3) Do not add information not present in the input.\n"
                "4) Output only the translated subtitle text.\n\n"
                f"Input subtitle:\n{text}"
            ),
        )

    def _build_easy_ja_prompt(self, text: str) -> _PromptSpec:
        return _PromptSpec(
            system=(
                "あなたは字幕のやさしい日本語変換アシスタントです。"
                "学習者が理解しやすいことを最優先にしてください。"
            ),
            user=(
                "以下の字幕を『やさしい日本語』に変換してください。\n"
                "目的: 日本語学習者や非専門家が、意味を保ったまま理解できること。\n"
                "必須ルール:\n"
                "1) 内容の事実関係を変えない（数値・固有名詞・否定は保持）。\n"
                "2) 1文を短く、難語はやさしい言い換えを使う。\n"
                "3) 専門語を残す場合は短い説明を付ける。\n"
                "4) 入力にない情報を追加しない。\n"
                "5) 出力は変換後テキストのみ。\n\n"
                f"入力字幕:\n{text}"
            ),
        )

    async def _call_openai(self, prompt: _PromptSpec) -> str:
        url = self._build_chat_completion_url()
        payload = self._build_chat_completion_payload(prompt)

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
            reason = "llm_rate_limited" if exc.code == 429 else "llm_http_error"
            raise CaptionTransformLLMError(
                reason=reason,
                message="caption transform http error",
                retry_after_seconds=self._parse_retry_after_seconds(exc),
            ) from exc
        except URLError as exc:
            raise CaptionTransformLLMError(
                reason="llm_network_error",
                message="caption transform network error",
            ) from exc
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise CaptionTransformLLMError(
                reason="llm_parse_error",
                message="caption transform parse error",
            ) from exc

    @staticmethod
    def _parse_retry_after_seconds(exc: HTTPError) -> float | None:
        header_value: str | None = None
        if exc.headers is not None:
            header_value = exc.headers.get("Retry-After")
        if not header_value:
            return None
        try:
            parsed = float(header_value.strip())
        except ValueError:
            return None
        if parsed <= 0:
            return None
        return parsed

    async def _call_openai_with_retry(self, prompt: _PromptSpec) -> str:
        attempts = self.MAX_RETRY_ATTEMPTS + 1
        for attempt in range(1, attempts + 1):
            try:
                return await self._call_openai(prompt)
            except CaptionTransformLLMError as exc:
                if (
                    exc.reason not in self.RETRYABLE_ERROR_REASONS
                    or attempt >= attempts
                ):
                    raise
                delay_seconds = self._compute_retry_delay_seconds(
                    exc=exc,
                    attempt=attempt,
                )
                logger.info(
                    "caption_transform_retrying reason=%s attempt=%d/%d delay=%.2fs",
                    exc.reason,
                    attempt,
                    attempts,
                    delay_seconds,
                )
                await asyncio.sleep(delay_seconds)
        raise RuntimeError("unreachable")

    def _compute_retry_delay_seconds(
        self,
        *,
        exc: CaptionTransformLLMError,
        attempt: int,
    ) -> float:
        if (
            exc.retry_after_seconds is not None
            and exc.retry_after_seconds > 0
        ):
            return min(exc.retry_after_seconds, self.RETRY_MAX_DELAY_SECONDS)
        exponential = self.RETRY_BASE_DELAY_SECONDS * (2 ** max(0, attempt - 1))
        return min(exponential, self.RETRY_MAX_DELAY_SECONDS)

    def _build_chat_completion_payload(
        self, prompt: _PromptSpec
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "messages": [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            "max_completion_tokens": 400,
        }
        if self._model.strip().lower().startswith("gpt-5"):
            payload["reasoning_effort"] = "minimal"
        return payload

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

    def _apply_local_fallback(self, *, text: str, target_lang_mode: str) -> str:
        if target_lang_mode == "en":
            return self._fallback_en(text)
        if target_lang_mode == "easy-ja":
            return self._fallback_easy_ja(text)
        return text

    def _fallback_en(self, text: str) -> str:
        out = text
        for source, target in self._EN_GLOSSARY:
            out = out.replace(source, target)
        return out

    def _fallback_easy_ja(self, text: str) -> str:
        out = text
        for source, target in self._EASY_JA_GLOSSARY:
            out = out.replace(source, target)
        return out
