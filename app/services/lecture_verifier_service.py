"""Lecture verifier service using Azure OpenAI for citation validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.schemas.lecture_qa import LectureSource

__all__ = [
    "LectureVerifierService",
    "AzureOpenAILectureVerifierService",
    "LectureVerificationResult",
]


@dataclass
class LectureVerificationResult:
    """Result of citation verification."""

    passed: bool
    summary: str
    unsupported_claims: list[str]
    corrected_answer: str | None = None  # Set if repair was attempted


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

    DEFAULT_MODEL = "gpt-4o"
    DEFAULT_MAX_TOKENS = 800
    DEFAULT_TEMPERATURE = 0.3  # Lower for verification
    DEFAULT_TIMEOUT_SECONDS = 30

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
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
            # No sources to verify against
            return LectureVerificationResult(
                passed=False,
                summary="検証用のソースがありません。",
                unsupported_claims=[answer],
            )

        # Build verification prompt
        prompt = self._build_prompt(question, answer, sources)

        # Call Azure OpenAI for verification
        verification = await self._call_openai_verification(prompt)

        # Parse verification result
        return self._parse_verification_result(verification, answer, sources)

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
        """Call Azure OpenAI API for verification.

        Note: This is a placeholder implementation.
        Real implementation should use openai.AsyncAzureOpenAI.
        """
        # TODO: Implement real Azure OpenAI call with JSON response
        # from openai import AsyncAzureOpenAI
        # client = AsyncAzureOpenAI(...)
        # response = await client.chat.completions.create(
        #     model=self._model,
        #     messages=[{"role": "user", "content": prompt}],
        #     response_format={"type": "json_object"},
        #     ...
        # )
        # return response.choices[0].message.content

        # Placeholder return (simulating successful verification)
        return '{"passed": true, "summary": "回答は講義資料に基づいています。", "unsupported_claims": []}'

    def _parse_verification_result(
        self,
        verification_json: str,
        answer: str,
        sources: list[LectureSource],
    ) -> LectureVerificationResult:
        """Parse JSON verification result into result object.

        Args:
            verification_json: JSON string from LLM
            answer: Original answer (for repair)
            sources: Sources (for repair)

        Returns:
            Parsed verification result
        """
        import json

        try:
            data = json.loads(verification_json)
            passed = data.get("passed", True)
            summary = data.get("summary", "検証が完了しました。")
            unsupported = data.get("unsupported_claims", [])

            return LectureVerificationResult(
                passed=passed,
                summary=summary,
                unsupported_claims=unsupported,
            )
        except (json.JSONDecodeError, KeyError):
            # Parse error - conservatively fail
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

        prompt = self._build_repair_prompt(
            question, answer, sources, unsupported_claims
        )

        # Call Azure OpenAI for repair
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
        """Call Azure OpenAI API for answer repair.

        Note: This is a placeholder implementation.
        """
        # TODO: Implement real Azure OpenAI call
        return None
