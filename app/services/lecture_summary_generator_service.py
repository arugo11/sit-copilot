"""Lecture summary generator service using Azure OpenAI for 30-second summaries."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.core.azure_openai_config import ValidationResult, validate_openai_config

__all__ = [
    "LectureSummaryGeneratorService",
    "AzureOpenAILectureSummaryGeneratorService",
    "UnavailableLectureSummaryGeneratorService",
    "LectureSummaryResult",
    "LectureSummaryGeneratorError",
]

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.models.speech_event import SpeechEvent
    from app.models.visual_event import VisualEvent


@dataclass
class LectureSummaryResult:
    """Generated lecture summary with evidence tags."""

    summary: str
    key_terms: list[str]
    evidence_tags: list[
        dict[str, str]
    ]  # {"type": "speech|slide|board", "timestamp": "...", "text": "..."}


class LectureSummaryGeneratorError(RuntimeError):
    """Raised when Azure OpenAI summary generation fails."""


class LectureSummaryGeneratorService(Protocol):
    """Interface for generating LLM-powered lecture summaries."""

    async def generate_summary(
        self,
        speech_events: list[SpeechEvent],
        visual_events: list[VisualEvent],
        lang_mode: str,
    ) -> LectureSummaryResult:
        """Generate LLM-powered summary with evidence tags.

        Args:
            speech_events: Finalized speech transcription events in the window
            visual_events: OCR events from slides/board in the window
            lang_mode: Language mode (ja, easy-ja, en)

        Returns:
            Generated summary with key terms and evidence tags

        Raises:
            LectureSummaryGeneratorError: If generation fails
        """
        ...


class UnavailableLectureSummaryGeneratorService:
    """Fail-closed summary generator used when Azure backend is unavailable."""

    def __init__(self, reason: str) -> None:
        self._reason = reason

    async def generate_summary(
        self,
        speech_events: list[SpeechEvent],
        visual_events: list[VisualEvent],
        lang_mode: str,
    ) -> LectureSummaryResult:
        del speech_events, visual_events, lang_mode
        raise LectureSummaryGeneratorError(self._reason)


class AzureOpenAILectureSummaryGeneratorService:
    """Azure OpenAI-based lecture summary generator with evidence attribution."""

    DEFAULT_MODEL = "gpt-4o"
    DEFAULT_MAX_TOKENS = 800
    DEFAULT_TEMPERATURE = 0
    DEFAULT_TIMEOUT_SECONDS = 30
    DEFAULT_API_VERSION = "2024-10-21"
    MAX_SUMMARY_CHARS = 600

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        account_name: str = "",
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        api_version: str = DEFAULT_API_VERSION,
    ) -> None:
        """Initialize Azure OpenAI summary generator.

        Args:
            api_key: Azure OpenAI API key
            endpoint: Azure OpenAI endpoint URL
            model: Model deployment name
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0 for factual summaries)
            timeout_seconds: Request timeout
            api_version: Azure OpenAI API version
        """
        self._api_key = api_key
        self._endpoint = endpoint
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._timeout_seconds = timeout_seconds
        self._api_version = api_version
        self._validation = self._validate_configuration(account_name=account_name)
        if not self._validation.is_valid:
            logger.warning(
                "azure_openai_summary_config_invalid reason=%s",
                self._validation.reason,
            )

    async def generate_summary(
        self,
        speech_events: list[SpeechEvent],
        visual_events: list[VisualEvent],
        lang_mode: str,
    ) -> LectureSummaryResult:
        """Generate LLM-powered summary with evidence tags.

        Args:
            speech_events: Finalized speech transcription events in the window
            visual_events: OCR events from slides/board in the window
            lang_mode: Language mode (ja, easy-ja, en)

        Returns:
            Generated summary with key terms and evidence tags

        Raises:
            LectureSummaryGeneratorError: If Azure OpenAI is unavailable or generation fails
        """
        if not self._is_azure_openai_ready():
            raise LectureSummaryGeneratorError(
                "azure openai is not configured or unavailable"
            )

        prompt = self._build_prompt(speech_events, visual_events, lang_mode)
        response_json = await self._call_openai(prompt)

        return self._parse_response(response_json)

    def _build_prompt(
        self,
        speech_events: list[SpeechEvent],
        visual_events: list[VisualEvent],
        lang_mode: str,
    ) -> str:
        """Build Japanese lecture summarization prompt with structured sections."""
        speech_section = self._format_speech_events(speech_events)
        visual_section = self._format_visual_events(visual_events)

        instructions = self._get_instructions_for_lang_mode(lang_mode)

        return f"""あなたは講義の要約を専門とするAIアシスタントです。

以下の講義コンテンツ（発言、スライド、板書）を要約し、重要なポイントを抽出してください。

{speech_section}

{visual_section}

要件:
- {instructions}
- 重要なキーワードを3〜5つ抽出してください
- 各ポイントにタイムスタンプを引用して情報の出典を明示してください
- 出典は [発言:05:23], [スライド:03:10], [板書:08:30] の形式で明示してください

出力形式 (JSON):
{{
    "summary": "全体の要約（600文字以内）",
    "key_terms": ["キーワード1", "キーワード2", "キーワード3"],
    "evidence": [
        {{"type": "speech", "timestamp": "05:23", "text": "該当する発言の抜粋"}},
        {{"type": "slide", "timestamp": "03:10", "text": "該当するスライドの抜粋"}},
        {{"type": "board", "timestamp": "08:30", "text": "該当する板書の抜粋"}}
    ]
}}

JSONのみを出力してください。"""

    def _format_speech_events(self, speech_events: list[SpeechEvent]) -> str:
        """Format speech events for the prompt."""
        if not speech_events:
            return "【発言】\n（この区間に発言はありません）"

        lines = ["【発言】"]
        for event in speech_events:
            timestamp = self._format_timestamp_ms(event.start_ms)
            lines.append(f"- [{timestamp}] {event.text}")
        return "\n".join(lines)

    def _format_visual_events(self, visual_events: list[VisualEvent]) -> str:
        """Format visual events for the prompt, grouped by source type."""
        if not visual_events:
            return "【スライド・板書】\n（この区間にスライド・板書はありません）"

        slides: list[VisualEvent] = []
        boards: list[VisualEvent] = []

        for event in visual_events:
            if event.source == "slide":
                slides.append(event)
            elif event.source == "board":
                boards.append(event)

        lines = ["【スライド・板書】"]

        if slides:
            lines.append("スライド:")
            for event in slides:
                timestamp = self._format_timestamp_ms(event.timestamp_ms)
                lines.append(f"- [{timestamp}] {event.ocr_text}")

        if boards:
            lines.append("板書:")
            for event in boards:
                timestamp = self._format_timestamp_ms(event.timestamp_ms)
                lines.append(f"- [{timestamp}] {event.ocr_text}")

        if not slides and not boards:
            lines.append("（この区間にスライド・板書はありません）")

        return "\n".join(lines)

    def _format_timestamp_ms(self, timestamp_ms: int) -> str:
        """Format millisecond timestamp to MM:SS string."""
        total_seconds = timestamp_ms // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def _get_instructions_for_lang_mode(self, lang_mode: str) -> str:
        """Get summary instructions based on language mode."""
        if lang_mode == "easy-ja":
            return "やさしい日本語で600文字以内で要約してください。小学生にもわかるように説明してください。"
        elif lang_mode == "en":
            return "Summarize in English within 600 characters. Focus on key points."
        return "600文字以内で要約してください。簡潔かつ明確にまとめてください。"

    async def _call_openai(self, prompt: str) -> dict[str, object]:
        """Call Azure OpenAI chat completion endpoint with JSON response format.

        Args:
            prompt: The formatted prompt to send

        Returns:
            Parsed JSON response from Azure OpenAI

        Raises:
            LectureSummaryGeneratorError: If the API call fails
        """
        url = self._build_chat_completion_url()
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a lecture summarization assistant. "
                        "Always respond with valid JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "response_format": {"type": "json_object"},
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
            return json.loads(raw)
        except HTTPError as exc:
            logger.warning(
                "azure_openai_summary_http_error status=%s",
                getattr(exc, "code", "unknown"),
            )
            raise LectureSummaryGeneratorError(
                "azure openai summary request failed"
            ) from exc
        except URLError as exc:
            logger.warning("azure_openai_summary_network_error")
            raise LectureSummaryGeneratorError(
                "azure openai summary network failure"
            ) from exc
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning("azure_openai_summary_parse_error")
            raise LectureSummaryGeneratorError(
                "azure openai summary parse failure"
            ) from exc

    def _is_azure_openai_ready(self) -> bool:
        """Return whether Azure OpenAI runtime call should be attempted."""
        return self._validation.is_valid

    def _build_chat_completion_url(self) -> str:
        """Build the chat completion URL for Azure OpenAI."""
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

    def _parse_response(self, response_json: dict[str, object]) -> LectureSummaryResult:
        """Parse Azure OpenAI JSON response and validate structure.

        Args:
            response_json: Raw response JSON from Azure OpenAI

        Returns:
            Parsed and validated summary result

        Raises:
            LectureSummaryGeneratorError: If response is invalid or missing required fields
        """
        try:
            choices = response_json.get("choices")
            if not isinstance(choices, list) or not choices:
                raise ValueError("missing choices")

            first_choice = choices[0]
            if not isinstance(first_choice, dict):
                raise ValueError("invalid choice payload")

            first_choice_dict = {str(key): value for key, value in first_choice.items()}
            message = first_choice_dict.get("message")
            if not isinstance(message, dict):
                raise ValueError("missing message")

            message_dict = {str(key): value for key, value in message.items()}
            content = message_dict.get("content")
            if not isinstance(content, str):
                raise ValueError("missing content")

            # Parse the JSON content
            result = json.loads(content)

            summary = result.get("summary", "")
            if not isinstance(summary, str):
                raise ValueError("summary must be a string")

            # Enforce 600-char limit server-side
            if len(summary) > self.MAX_SUMMARY_CHARS:
                summary = summary[: self.MAX_SUMMARY_CHARS]

            key_terms = result.get("key_terms", [])
            if not isinstance(key_terms, list):
                raise ValueError("key_terms must be a list")

            # Validate key_terms are strings
            validated_key_terms: list[str] = []
            for term in key_terms:
                if isinstance(term, str) and term.strip():
                    validated_key_terms.append(term.strip())

            evidence = result.get("evidence", [])
            if not isinstance(evidence, list):
                raise ValueError("evidence must be a list")

            # Validate evidence tags
            allowed_types = {"speech", "slide", "board"}
            validated_evidence: list[dict[str, str]] = []
            for tag in evidence:
                if not isinstance(tag, dict):
                    continue

                tag_type = tag.get("type", "")
                if tag_type not in allowed_types:
                    continue

                timestamp = tag.get("timestamp", "")
                text = tag.get("text", "")

                if isinstance(timestamp, str) and isinstance(text, str):
                    validated_evidence.append(
                        {
                            "type": tag_type,
                            "timestamp": timestamp,
                            "text": text,
                        }
                    )

            return LectureSummaryResult(
                summary=summary,
                key_terms=validated_key_terms,
                evidence_tags=validated_evidence,
            )

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning("azure_openai_summary_response_parse_error")
            raise LectureSummaryGeneratorError(
                "azure openai summary response parse failure"
            ) from exc
