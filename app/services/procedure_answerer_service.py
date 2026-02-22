"""Procedure answerer service using Azure OpenAI."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.core.azure_openai_config import ValidationResult, validate_openai_config
from app.schemas.procedure import ProcedureConfidence, ProcedureSource

__all__ = [
    "ProcedureAnswerDraft",
    "ProcedureAnswererService",
    "AzureOpenAIProcedureAnswererService",
    "ProcedureAnswererError",
]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcedureAnswerDraft:
    """Answerer output before API response packaging."""

    answer: str
    confidence: ProcedureConfidence
    action_next: str


class ProcedureAnswererError(RuntimeError):
    """Raised when procedure answer generation fails."""


class ProcedureAnswererService(Protocol):
    """Interface for generating grounded procedure answers."""

    async def answer(
        self, query: str, lang_mode: str, sources: list[ProcedureSource]
    ) -> ProcedureAnswerDraft:
        """Generate an answer based on provided sources only."""
        ...


class AzureOpenAIProcedureAnswererService:
    """Azure OpenAI answerer for procedure QA."""

    DEFAULT_MODEL = "gpt-5-nano"
    DEFAULT_MAX_TOKENS = 800
    DEFAULT_TEMPERATURE = 0.2
    DEFAULT_TIMEOUT_SECONDS = 30
    DEFAULT_API_VERSION = "2024-05-01-preview"
    DEFAULT_ACTION_NEXT = (
        "教務課または公式ポータルで最新の手続き情報を確認してください。"
    )

    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str,
        account_name: str = "",
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        api_version: str = DEFAULT_API_VERSION,
    ) -> None:
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
                "azure_openai_procedure_answer_config_invalid reason=%s",
                self._validation.reason,
            )

    async def answer(
        self,
        query: str,
        lang_mode: str,
        sources: list[ProcedureSource],
    ) -> ProcedureAnswerDraft:
        """Generate grounded procedure answer in strict JSON format."""
        if not sources:
            raise ProcedureAnswererError(
                "procedure answer requires at least one source"
            )
        if not self._is_azure_openai_ready():
            raise ProcedureAnswererError("azure openai configuration is unavailable")

        prompt = self._build_prompt(
            query=query,
            lang_mode=lang_mode,
            sources=sources,
        )
        raw_content = await self._call_openai(prompt)
        return self._parse_draft(raw_content)

    def _build_prompt(
        self,
        *,
        query: str,
        lang_mode: str,
        sources: list[ProcedureSource],
    ) -> str:
        language_instruction = self._language_instruction(lang_mode)
        source_lines = [
            f"- [{source.source_id}] {source.title} / {source.section}: {source.snippet}"
            for source in sources
        ]
        joined_sources = "\n".join(source_lines)

        return f"""あなたは大学の手続きQAアシスタントです。

以下の根拠ソースの内容だけを使って回答してください。
根拠にない内容を推測で補わないでください。

質問:
{query}

根拠ソース:
{joined_sources}

出力言語:
{language_instruction}

次のJSONのみを返してください:
{{
  "answer": "回答本文",
  "confidence": "high|medium|low",
  "action_next": "次に取る行動"
}}
"""

    @staticmethod
    def _language_instruction(lang_mode: str) -> str:
        if lang_mode == "en":
            return "English"
        if lang_mode == "easy-ja":
            return "やさしい日本語"
        return "日本語"

    async def _call_openai(self, prompt: str) -> str:
        """Call Azure OpenAI and return assistant content."""
        url = self._build_chat_completion_url()
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a grounded procedure QA assistant. "
                        "Use only provided sources and return JSON."
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
                body_bytes = response.read()
                if not isinstance(body_bytes, bytes):
                    raise ProcedureAnswererError("azure openai response is not bytes")
                return body_bytes.decode("utf-8")

        try:
            raw = await asyncio.to_thread(_run_request)
            response_json = json.loads(raw)
            return self._extract_content(response_json).strip()
        except HTTPError as exc:
            logger.warning(
                "azure_openai_procedure_answer_http_error status=%s",
                getattr(exc, "code", "unknown"),
            )
            raise ProcedureAnswererError(
                "azure openai procedure request failed"
            ) from exc
        except URLError as exc:
            logger.warning("azure_openai_procedure_answer_network_error")
            raise ProcedureAnswererError(
                "azure openai procedure network failure"
            ) from exc
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning("azure_openai_procedure_answer_parse_error")
            raise ProcedureAnswererError(
                "azure openai procedure parse failure"
            ) from exc

    def _build_chat_completion_url(self) -> str:
        endpoint = self._validation.normalized_endpoint.rstrip("/")
        deployment = quote(self._model.strip(), safe="")
        return (
            f"{endpoint}/openai/deployments/{deployment}/chat/completions"
            f"?api-version={self._api_version}"
        )

    def _is_azure_openai_ready(self) -> bool:
        return self._validation.is_valid

    def _validate_configuration(self, *, account_name: str) -> ValidationResult:
        return validate_openai_config(
            api_key=self._api_key,
            endpoint=self._endpoint,
            deployment=self._model,
            account_name=account_name,
        )

    def _extract_content(self, response_json: dict[str, Any]) -> str:
        choices = response_json.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("missing choices")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ValueError("invalid choice payload")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ValueError("missing message")
        content = message.get("content")
        if isinstance(content, str):
            return str(content)
        if isinstance(content, list):
            parts: list[str] = []
            for part in content:
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
            if parts:
                return "\n".join(parts)
        raise ValueError("missing content")

    def _parse_draft(self, content: str) -> ProcedureAnswerDraft:
        try:
            payload = json.loads(content)
            if not isinstance(payload, dict):
                raise ValueError("payload must be dict")
            answer = str(payload.get("answer", "")).strip()
            if not answer:
                raise ValueError("answer is empty")
            action_next_raw = str(payload.get("action_next", "")).strip()
            action_next = action_next_raw or self.DEFAULT_ACTION_NEXT
            confidence = self._normalize_confidence(payload.get("confidence"))
            return ProcedureAnswerDraft(
                answer=answer,
                confidence=confidence,
                action_next=action_next,
            )
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ProcedureAnswererError("invalid procedure answer payload") from exc

    @staticmethod
    def _normalize_confidence(value: Any) -> ProcedureConfidence:
        if isinstance(value, str):
            lowered = value.strip().lower()
            confidence_map: dict[str, ProcedureConfidence] = {
                "high": "high",
                "medium": "medium",
                "low": "low",
            }
            if lowered in confidence_map:
                return confidence_map[lowered]
        return "medium"
