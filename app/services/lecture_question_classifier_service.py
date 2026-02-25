"""Question classifier for lecture QA retrieval policy optimization."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Literal, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.core.azure_openai_config import ValidationResult, validate_openai_config

__all__ = [
    "LectureQuestionClassifierService",
    "AzureOpenAILectureQuestionClassifierService",
    "HeuristicLectureQuestionClassifierService",
    "LectureQuestionClassification",
]

logger = logging.getLogger(__name__)

QuestionType = Literal[
    "factoid",
    "definition",
    "comparison",
    "causal",
    "procedural",
    "general",
]


@dataclass(frozen=True)
class LectureQuestionClassification:
    """Classification output used to tune retrieval and citation policy."""

    question_type: QuestionType
    confidence: float


class LectureQuestionClassifierService(Protocol):
    """Classify user question intent for adaptive QA policy."""

    async def classify(self, *, question: str, lang_mode: str) -> LectureQuestionClassification:
        """Classify a lecture question."""
        ...


class HeuristicLectureQuestionClassifierService:
    """Lightweight fallback classifier for when Azure OpenAI is unavailable."""

    _FACTOID_PATTERNS = (
        r"いつ",
        r"何年",
        r"何月",
        r"何日",
        r"どこ",
        r"だれ",
        r"誰",
        r"when",
        r"what year",
        r"what date",
        r"which year",
        r"who",
        r"where",
        r"how many",
        r"how much",
    )
    _COMPARISON_PATTERNS = (r"違い", r"比較", r"どちら", r"compare", r"difference")
    _CAUSAL_PATTERNS = (r"なぜ", r"どうして", r"理由", r"why", r"reason")
    _PROCEDURAL_PATTERNS = (
        r"手順",
        r"方法",
        r"どうやって",
        r"やり方",
        r"steps",
        r"how to",
        r"procedure",
    )
    _DEFINITION_PATTERNS = (r"とは", r"定義", r"意味", r"what is", r"define")

    async def classify(
        self,
        *,
        question: str,
        lang_mode: str,
    ) -> LectureQuestionClassification:
        _ = lang_mode
        normalized = question.strip().lower()
        if not normalized:
            return LectureQuestionClassification(question_type="general", confidence=0.0)

        if self._matches_any(normalized, self._FACTOID_PATTERNS):
            return LectureQuestionClassification(question_type="factoid", confidence=0.7)
        if self._matches_any(normalized, self._COMPARISON_PATTERNS):
            return LectureQuestionClassification(question_type="comparison", confidence=0.7)
        if self._matches_any(normalized, self._CAUSAL_PATTERNS):
            return LectureQuestionClassification(question_type="causal", confidence=0.7)
        if self._matches_any(normalized, self._PROCEDURAL_PATTERNS):
            return LectureQuestionClassification(question_type="procedural", confidence=0.7)
        if self._matches_any(normalized, self._DEFINITION_PATTERNS):
            return LectureQuestionClassification(question_type="definition", confidence=0.7)
        return LectureQuestionClassification(question_type="general", confidence=0.6)

    @staticmethod
    def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
        return any(re.search(pattern, text) for pattern in patterns)


class AzureOpenAILectureQuestionClassifierService:
    """Azure OpenAI question classifier with heuristic fallback."""

    DEFAULT_MODEL = "gpt-5-nano"
    DEFAULT_TIMEOUT_SECONDS = 20
    DEFAULT_API_VERSION = "2024-05-01-preview"

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        account_name: str = "",
        model: str = DEFAULT_MODEL,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        api_version: str = DEFAULT_API_VERSION,
        confidence_threshold: float = 0.65,
        fallback: LectureQuestionClassifierService | None = None,
    ) -> None:
        self._api_key = api_key
        self._endpoint = endpoint
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._api_version = api_version
        self._confidence_threshold = max(0.0, min(1.0, confidence_threshold))
        self._fallback = fallback or HeuristicLectureQuestionClassifierService()
        self._validation = self._validate_configuration(account_name=account_name)
        if not self._validation.is_valid:
            logger.warning(
                "azure_openai_question_classifier_config_invalid reason=%s",
                self._validation.reason,
            )

    async def classify(self, *, question: str, lang_mode: str) -> LectureQuestionClassification:
        if not question.strip():
            return LectureQuestionClassification(question_type="general", confidence=0.0)

        if not self._is_azure_openai_ready():
            return await self._fallback.classify(question=question, lang_mode=lang_mode)

        prompt = self._build_prompt(question=question, lang_mode=lang_mode)
        try:
            response = await self._call_openai(prompt)
            parsed = self._parse_response(response)
            if parsed.confidence < self._confidence_threshold:
                return LectureQuestionClassification(question_type="general", confidence=parsed.confidence)
            return parsed
        except (RuntimeError, ValueError, TypeError, json.JSONDecodeError):
            return await self._fallback.classify(question=question, lang_mode=lang_mode)

    def _build_prompt(self, *, question: str, lang_mode: str) -> str:
        return f"""You classify lecture QA questions into one intent label.

Question: {question}
Language mode: {lang_mode}

Allowed labels:
- factoid: asks for a specific date, number, person, location, or short factual item
- definition: asks what a term/concept means
- comparison: asks differences/similarities between two or more items
- causal: asks why/how something happens (reason/mechanism)
- procedural: asks steps or method to do something
- general: anything else

Rules:
- Choose exactly one label from the list
- Prefer factoid for "when/what year/who/where/how many" style questions
- Return JSON only

Output JSON format:
{{
  "question_type": "factoid|definition|comparison|causal|procedural|general",
  "confidence": 0.0
}}"""

    async def _call_openai(self, prompt: str) -> dict[str, object]:
        url = self._build_chat_completion_url()
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a strict classifier. "
                        "Return valid JSON only, with one label and confidence."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "max_completion_tokens": 120,
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
            raw = await asyncio.to_thread(_run_request)
            return json.loads(raw)
        except HTTPError as exc:
            logger.warning(
                "azure_openai_question_classifier_http_error status=%s",
                getattr(exc, "code", "unknown"),
            )
            raise RuntimeError("azure openai classifier request failed") from exc
        except URLError as exc:
            logger.warning("azure_openai_question_classifier_network_error")
            raise RuntimeError("azure openai classifier network failure") from exc

    def _parse_response(
        self,
        response_json: dict[str, object],
    ) -> LectureQuestionClassification:
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
        if not isinstance(content, str):
            raise ValueError("missing content")

        parsed = json.loads(content)
        question_type = str(parsed.get("question_type", "general")).strip().lower()
        confidence_raw = parsed.get("confidence", 0.0)

        allowed: set[str] = {
            "factoid",
            "definition",
            "comparison",
            "causal",
            "procedural",
            "general",
        }
        if question_type not in allowed:
            question_type = "general"

        confidence = float(confidence_raw)
        confidence = max(0.0, min(1.0, confidence))

        return LectureQuestionClassification(
            question_type=cast(QuestionType, question_type),
            confidence=confidence,
        )

    def _is_azure_openai_ready(self) -> bool:
        return self._validation.is_valid

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
