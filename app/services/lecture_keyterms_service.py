"""Lecture key terms extraction service using Azure OpenAI."""

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
    "LectureKeyTermsService",
    "AzureOpenAILectureKeyTermsService",
    "UnavailableLectureKeyTermsService",
    "ResilientLectureKeyTermsService",
    "LectureKeyTermsResult",
    "LectureKeyTermsError",
]

logger = logging.getLogger(__name__)


@dataclass
class LectureKeyTermsResult:
    """Extracted key terms with explanations."""

    key_terms: list[
        dict[str, str]
    ]  # [{"term": "...", "explanation": "...", "translation": "..."}]
    detected_terms: list[str]


class LectureKeyTermsError(RuntimeError):
    """Raised when Azure OpenAI key terms extraction fails."""


class LectureKeyTermsService(Protocol):
    """Interface for extracting key terms from transcript."""

    async def extract_key_terms(
        self,
        transcript_text: str,
        lang_mode: str,
    ) -> LectureKeyTermsResult:
        """Extract key terms from transcript and generate explanations.

        Args:
            transcript_text: Transcript text to analyze
            lang_mode: Language mode (ja, easy-ja, en)

        Returns:
            Extracted key terms with explanations

        Raises:
            LectureKeyTermsError: If extraction fails
        """
        ...


class UnavailableLectureKeyTermsService:
    """Fail-closed key terms extractor used when Azure backend is unavailable."""

    def __init__(self, reason: str) -> None:
        self._reason = reason

    async def extract_key_terms(
        self,
        transcript_text: str,
        lang_mode: str,
    ) -> LectureKeyTermsResult:
        logger.info(
            "keyterms_fallback_used reason=%s transcript_len=%s",
            self._reason,
            len(transcript_text),
        )
        del transcript_text, lang_mode
        return LectureKeyTermsResult(key_terms=[], detected_terms=[])


class AzureOpenAILectureKeyTermsService:
    """Azure OpenAI-based key terms extractor with explanations."""

    DEFAULT_MODEL = "gpt-5-nano"
    DEFAULT_MAX_TOKENS = 800
    DEFAULT_TEMPERATURE = 0
    DEFAULT_TIMEOUT_SECONDS = 30
    DEFAULT_API_VERSION = "2024-05-01-preview"

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
        """Initialize Azure OpenAI key terms extractor.

        Args:
            api_key: Azure OpenAI API key
            endpoint: Azure OpenAI endpoint URL
            model: Model deployment name
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0 for factual extraction)
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
        self._last_usage: LLMUsage | None = None
        self._validation = self._validate_configuration(account_name=account_name)
        if not self._validation.is_valid:
            logger.warning(
                "azure_openai_keyterms_config_invalid reason=%s",
                self._validation.reason,
            )

    async def extract_key_terms(
        self,
        transcript_text: str,
        lang_mode: str,
    ) -> LectureKeyTermsResult:
        """Extract key terms from transcript and generate explanations.

        Args:
            transcript_text: Transcript text to analyze
            lang_mode: Language mode (ja, easy-ja, en)

        Returns:
            Extracted key terms with explanations

        Raises:
            LectureKeyTermsError: If Azure OpenAI is unavailable or extraction fails
        """
        if not self._is_azure_openai_ready():
            raise LectureKeyTermsError("azure openai is not configured or unavailable")

        prompt = self._build_prompt(transcript_text, lang_mode)
        response_json = await self._call_openai(prompt)

        return self._parse_response(response_json, transcript_text=transcript_text)

    def _build_prompt(
        self,
        transcript_text: str,
        lang_mode: str,
    ) -> str:
        """Build key terms extraction prompt."""

        instructions = self._get_instructions_for_lang_mode(lang_mode)

        return f"""あなたは講義の専門用語を抽出して説明するAIアシスタントです。

以下の講義トランスクリプトを分析し、聴講者が理解するのに難しそうな専門用語や重要な概念を抽出してください。

トランスクリプト:
{transcript_text}

要件:
- {instructions}
- 専門用語や重要な概念を最大3つ抽出してください
- すべての用語を説明する必要はありません。理解するのが難しい用語や、講義の理解に重要な用語のみを選択してください
- 抽出する term は、必ず上記トランスクリプトに実際に登場する語句をそのまま使ってください（言い換え・補完・推測で新しい語を追加しない）
- 用語がない場合は空のリストを返してください

出力形式 (JSON):
{{
    "key_terms": [
        {{
            "term": "用語",
            "explanation": "初心者にもわかる説明（100文字以内）",
            "translation": "読み方や翻訳"
        }}
    ],
    "detected_terms": ["用語1", "用語2"]
}}

JSONのみを出力してください。"""

    def _get_instructions_for_lang_mode(self, lang_mode: str) -> str:
        """Get instructions based on language mode."""
        if lang_mode == "easy-ja":
            return "小学生にもわかるやさしい日本語で説明してください。漢字にはひらがなで読みを添えてください。"
        elif lang_mode == "en":
            return "Explain in simple English for non-native speakers."
        return "専門用語や重要な概念を簡潔に説明してください。漢字にはひらがなで読みを添えてください。"

    async def _call_openai(self, prompt: str) -> dict[str, object]:
        """Call Azure OpenAI chat completion endpoint.

        Args:
            prompt: The formatted prompt to send

        Returns:
            Parsed JSON response from Azure OpenAI

        Raises:
            LectureKeyTermsError: If the API call fails
        """
        url = self._build_chat_completion_url()
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a lecture key terms extractor. "
                        "Always respond with valid JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "max_completion_tokens": self._max_tokens,
            "reasoning_effort": "minimal",
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
            import asyncio

            raw = await asyncio.to_thread(_run_request)
            result = json.loads(raw)
            self._last_usage = extract_usage(result)
            return result
        except HTTPError as exc:
            logger.warning(
                "azure_openai_keyterms_http_error status=%s",
                getattr(exc, "code", "unknown"),
            )
            raise LectureKeyTermsError("azure openai key terms request failed") from exc
        except URLError as exc:
            logger.warning("azure_openai_keyterms_network_error")
            raise LectureKeyTermsError(
                "azure openai key terms network failure"
            ) from exc
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning("azure_openai_keyterms_parse_error")
            raise LectureKeyTermsError("azure openai key terms parse failure") from exc

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

    def _parse_response(
        self,
        response_json: dict[str, object],
        *,
        transcript_text: str,
    ) -> LectureKeyTermsResult:
        """Parse Azure OpenAI JSON response and validate structure.

        Args:
            response_json: Raw response JSON from Azure OpenAI

        Returns:
            Parsed and validated key terms result

        Raises:
            LectureKeyTermsError: If response is invalid or missing required fields
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

            # Some model variants may return a simplified schema such as:
            # {"keywords": ["...", "..."]} or {"important_words": [...]}
            simplified_terms: list[str] = []
            for candidate_key in ("keywords", "important_words", "重要語"):
                candidate = result.get(candidate_key)
                if isinstance(candidate, list):
                    simplified_terms = [
                        item.strip()
                        for item in candidate
                        if isinstance(item, str) and item.strip()
                    ]
                    if simplified_terms:
                        break

            key_terms = result.get("key_terms", [])
            if not isinstance(key_terms, list):
                raise ValueError("key_terms must be a list")

            transcript_compact = self._compact_text(transcript_text)

            # Validate key_terms
            validated_key_terms: list[dict[str, str]] = []
            for term in key_terms:
                if not isinstance(term, dict):
                    continue
                term_value = term.get("term", "")
                if not isinstance(term_value, str) or not term_value.strip():
                    continue
                cleaned_term = term_value.strip()
                # Fail-closed: only keep terms explicitly present in transcript.
                if cleaned_term not in transcript_text and self._compact_text(
                    cleaned_term
                ) not in transcript_compact:
                    continue
                validated_key_terms.append(
                    {
                        "term": cleaned_term,
                        "explanation": (
                            term.get("explanation", "")
                            if isinstance(term.get("explanation", ""), str)
                            else ""
                        ),
                        "translation": (
                            term.get("translation", term_value.strip())
                            if isinstance(term.get("translation", term_value.strip()), str)
                            else term_value.strip()
                        ),
                    }
                )

            if not validated_key_terms and simplified_terms:
                validated_key_terms = [
                    {
                        "term": term,
                        "explanation": "",
                        "translation": term,
                    }
                    for term in simplified_terms
                    if (
                        term in transcript_text
                        or self._compact_text(term) in transcript_compact
                    )
                ]

            detected_terms = result.get("detected_terms", [])
            if not isinstance(detected_terms, list):
                detected_terms = []

            validated_detected_terms: list[str] = []
            for term in detected_terms:
                if not isinstance(term, str) or not term.strip():
                    continue
                cleaned_term = term.strip()
                if cleaned_term not in transcript_text and self._compact_text(
                    cleaned_term
                ) not in transcript_compact:
                    continue
                validated_detected_terms.append(cleaned_term)

            if not validated_detected_terms and validated_key_terms:
                validated_detected_terms = [term["term"] for term in validated_key_terms]

            return LectureKeyTermsResult(
                key_terms=validated_key_terms,
                detected_terms=validated_detected_terms,
            )

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning("azure_openai_keyterms_response_parse_error")
            raise LectureKeyTermsError(
                "azure openai key terms response parse failure"
            ) from exc

    @staticmethod
    def _compact_text(value: str) -> str:
        return "".join(value.split())


class ResilientLectureKeyTermsService:
    """Primary + fallback key terms extractor with graceful degradation."""

    def __init__(
        self,
        primary: LectureKeyTermsService,
        fallback: LectureKeyTermsService,
    ) -> None:
        self._primary = primary
        self._fallback = fallback

    async def extract_key_terms(
        self,
        transcript_text: str,
        lang_mode: str,
    ) -> LectureKeyTermsResult:
        try:
            return await self._primary.extract_key_terms(
                transcript_text=transcript_text,
                lang_mode=lang_mode,
            )
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.warning(
                "keyterms_primary_failed_fallback_used error=%s",
                exc.__class__.__name__,
            )
            return await self._fallback.extract_key_terms(
                transcript_text=transcript_text,
                lang_mode=lang_mode,
            )
