"""Lecture verifier service using Azure OpenAI for citation validation."""

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
from app.schemas.lecture_qa import LectureSource

__all__ = [
    "LectureVerifierService",
    "AzureOpenAILectureVerifierService",
    "LectureVerificationResult",
    "LectureVerifierError",
]

logger = logging.getLogger(__name__)


@dataclass
class LectureVerificationResult:
    """Result of citation verification."""

    passed: bool
    summary: str
    unsupported_claims: list[str]
    corrected_answer: str | None = None  # Set if repair was attempted


class LectureVerifierError(RuntimeError):
    """Raised when Azure OpenAI verification call fails."""


class LectureVerifierService(Protocol):
    """Interface for verifying answer citations against sources."""

    async def verify(
        self,
        question: str,
        answer: str,
        sources: list[LectureSource],
    ) -> LectureVerificationResult:
        """Verify answer claims against provided sources."""
        ...

    async def repair_answer(
        self,
        question: str,
        answer: str,
        sources: list[LectureSource],
        unsupported_claims: list[str],
    ) -> str | None:
        """Attempt to repair answer using only verified claims.

        Returns repaired answer or None if repair fails.
        """
        ...


class AzureOpenAILectureVerifierService:
    """Azure OpenAI-based verifier for citation validation."""

    DEFAULT_MODEL = "gpt-5-nano"
    DEFAULT_MAX_TOKENS = 800
    DEFAULT_TEMPERATURE = 0.3  # Lower for verification
    DEFAULT_TIMEOUT_SECONDS = 30
    DEFAULT_API_VERSION = "2024-05-01-preview"
    LOCAL_SNIPPET_WINDOW = 12

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
        """Initialize Azure OpenAI verifier.

        Args:
            api_key: Azure OpenAI API key
            endpoint: Azure OpenAI endpoint URL
            model: Model deployment name
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (lower for verification)
            timeout_seconds: Request timeout
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
                "azure_openai_lecture_verify_config_invalid reason=%s",
                self._validation.reason,
            )

    async def verify(
        self,
        question: str,
        answer: str,
        sources: list[LectureSource],
    ) -> LectureVerificationResult:
        """Verify answer claims against provided sources.

        Args:
            question: Original question
            answer: Generated answer to verify
            sources: Source chunks used for answer generation

        Returns:
            Verification result with pass/fail status and details
        """
        if not sources:
            return LectureVerificationResult(
                passed=False,
                summary="検証用のソースがありません。",
                unsupported_claims=[answer],
            )

        prompt = self._build_prompt(question, answer, sources)
        if not self._is_azure_openai_ready():
            return self._local_verify(answer=answer, sources=sources)

        verification = await self._call_openai_verification(prompt)
        return self._parse_verification_result(verification, answer)

    def _build_prompt(
        self,
        question: str,
        answer: str,
        sources: list[LectureSource],
    ) -> str:
        """Build citation verification prompt."""
        sources_text = self._format_sources(sources)

        return f"""あなたは回答の正確性を検証する検証者です。

以下の講義資料（ソース）に基づいて、回答が正確かどうかを検証してください。

【講義資料（ソース）】
{sources_text}

【質問】
{question}

【回答】
{answer}

タスク:
1. 回答の主張を一つ一つ特定してください
2. 各主張が講義資料で支持されているか確認してください
3. サポートされていない主張があればリストアップしてください
4. 検証結果をJSON形式で出力してください:

出力形式:
{{
  "passed": true/false,
  "summary": "検証の要約（日本語）",
  "unsupported_claims": ["サポートされていない主張1", "主張2", ...]
}}

ルール:
- 推測や一般的知識は「サポートされていない」とみなしてください
- 講義資料に明記されていない情報は「サポートされていない」としてください
- 同意語や言い換えは「サポートされている」とみなしてください
"""

    def _format_sources(self, sources: list[LectureSource]) -> str:
        """Format sources for verification prompt."""
        lines = []
        for source in sources:
            ts = source.timestamp or "??:??"
            lines.append(f"[{ts}] {source.text}")
        return "\n".join(lines)

    async def _call_openai_verification(self, prompt: str) -> str:
        """Call Azure OpenAI API for verification JSON.

        Raises:
            LectureVerifierError: If remote call fails.
        """
        url = self._build_chat_completion_url()
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a strict groundedness verifier. Return only JSON."
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
            response_json = json.loads(raw)
            return self._extract_content(response_json).strip()
        except HTTPError as exc:
            logger.warning(
                "azure_openai_verify_http_error status=%s",
                getattr(exc, "code", "unknown"),
            )
            raise LectureVerifierError("azure openai verify request failed") from exc
        except URLError as exc:
            logger.warning("azure_openai_verify_network_error")
            raise LectureVerifierError("azure openai verify network failure") from exc
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning("azure_openai_verify_parse_error")
            raise LectureVerifierError("azure openai verify parse failure") from exc

    def _parse_verification_result(
        self,
        verification_json: str,
        answer: str,
    ) -> LectureVerificationResult:
        """Parse JSON verification result into result object.

        Args:
            verification_json: JSON string from LLM
            answer: Original answer (for repair)
            sources: Sources (for repair)

        Returns:
            Parsed verification result
        """
        try:
            data = json.loads(verification_json)
            if not isinstance(data, dict):
                raise ValueError("verification result is not a dict")
            passed_raw = data.get("passed", True)
            summary_raw = data.get("summary", "検証が完了しました。")
            unsupported_raw = data.get("unsupported_claims", [])
            passed = self._parse_passed_flag(passed_raw)
            summary = str(summary_raw).strip() or "検証が完了しました。"
            unsupported = self._normalize_unsupported_claims(unsupported_raw)
            if passed and unsupported:
                passed = False

            return LectureVerificationResult(
                passed=passed,
                summary=summary,
                unsupported_claims=unsupported,
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return LectureVerificationResult(
                passed=False,
                summary="検証結果の解析に失敗しました。",
                unsupported_claims=[answer],
            )

    async def repair_answer(
        self,
        question: str,
        answer: str,
        sources: list[LectureSource],
        unsupported_claims: list[str],
    ) -> str | None:
        """Attempt to repair answer using only verified claims.

        Args:
            question: Original question
            answer: Original answer
            sources: Source chunks
            unsupported_claims: Claims that were not supported

        Returns:
            Repaired answer using only supported information, or None if repair fails
        """
        if not sources:
            return None

        if not self._is_azure_openai_ready():
            return self._local_repair_answer(sources=sources)

        prompt = self._build_repair_prompt(
            question, answer, sources, unsupported_claims
        )
        repaired = await self._call_openai_repair(prompt)

        return repaired if repaired else None

    def _build_repair_prompt(
        self,
        question: str,
        answer: str,
        sources: list[LectureSource],
        unsupported_claims: list[str],
    ) -> str:
        """Build repair prompt."""
        sources_text = self._format_sources(sources)
        claims_text = "\n".join(f"- {c}" for c in unsupported_claims)

        return f"""あなたは回答を修正する編集者です。

元の回答には、講義資料でサポートされていない主張が含まれています。
講義資料に基づいた情報のみを使用して、回答を修正してください。

【講義資料（ソース）】
{sources_text}

【質問】
{question}

【元の回答】
{answer}

【サポートされていない主張】
{claims_text}

タスク:
- サポートされていない主張を削除してください
- 講義資料に基づいた情報のみを使用してください
- 回答の一貫性を保ってください
- 修正した回答を出力してください

修正が不可能な場合は「修正不可能」と出力してください。
"""

    async def _call_openai_repair(self, prompt: str) -> str | None:
        """Call Azure OpenAI API for answer repair."""
        url = self._build_chat_completion_url()
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You repair answers by removing unsupported claims and "
                        "keeping only evidence-backed statements."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
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
            repaired = self._extract_content(response_json).strip()
            if not repaired or repaired == "修正不可能":
                return None
            return repaired
        except HTTPError as exc:
            logger.warning(
                "azure_openai_repair_http_error status=%s",
                getattr(exc, "code", "unknown"),
            )
            raise LectureVerifierError("azure openai repair request failed") from exc
        except URLError as exc:
            logger.warning("azure_openai_repair_network_error")
            raise LectureVerifierError("azure openai repair network failure") from exc
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning("azure_openai_repair_parse_error")
            raise LectureVerifierError("azure openai repair parse failure") from exc

    def _local_verify(
        self,
        *,
        answer: str,
        sources: list[LectureSource],
    ) -> LectureVerificationResult:
        normalized_answer = self._normalize_text(answer)
        if not normalized_answer:
            return LectureVerificationResult(
                passed=False,
                summary="回答が空のため検証に失敗しました。",
                unsupported_claims=[answer],
            )

        matched = any(
            self._contains_source_fragment(
                answer_text=normalized_answer,
                source_text=self._normalize_text(source.text),
            )
            for source in sources
        )
        if matched:
            return LectureVerificationResult(
                passed=True,
                summary="ローカル検証で根拠との一致を確認しました。",
                unsupported_claims=[],
            )

        return LectureVerificationResult(
            passed=False,
            summary="ローカル検証で根拠一致を確認できませんでした。",
            unsupported_claims=[answer],
        )

    def _local_repair_answer(self, *, sources: list[LectureSource]) -> str | None:
        for source in sources:
            snippet = source.text.strip().replace("\n", " ")
            if snippet:
                clipped = snippet[:120]
                return f"講義資料では「{clipped}」と説明されています。"
        return None

    def _contains_source_fragment(self, *, answer_text: str, source_text: str) -> bool:
        if not source_text:
            return False
        window = min(self.LOCAL_SNIPPET_WINDOW, len(source_text))
        if window <= 0:
            return False
        for start in range(0, len(source_text) - window + 1):
            fragment = source_text[start : start + window]
            if fragment and fragment in answer_text:
                return True
        return False

    def _normalize_text(self, text: str) -> str:
        return "".join(text.lower().split())

    def _normalize_unsupported_claims(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        claims: list[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            normalized = item.strip()
            if normalized:
                claims.append(normalized)
        return claims

    def _parse_passed_flag(self, value: object) -> bool:
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized == "true":
                return True
            if normalized == "false":
                return False

        raise ValueError("passed must be a boolean value")

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

    def _extract_content(self, response_json: dict[str, object]) -> str:
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
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if not isinstance(part, dict):
                    continue
                part_dict = {str(key): value for key, value in part.items()}
                text = part_dict.get("text")
                if isinstance(text, str) and text.strip():
                    text_parts.append(text.strip())
            if text_parts:
                return "\n".join(text_parts)
        raise ValueError("missing content")
