"""Lecture follow-up service for context-aware query resolution."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.azure_openai_config import ValidationResult, validate_openai_config
from app.models.lecture_session import LectureSession
from app.models.qa_turn import QATurn
from app.services.observability.llm_usage import LLMUsage, extract_usage

__all__ = [
    "LectureFollowupService",
    "SqlAlchemyLectureFollowupService",
    "FollowupResolution",
    "LectureFollowupError",
]

logger = logging.getLogger(__name__)


@dataclass
class FollowupResolution:
    """Result of follow-up query resolution."""

    standalone_query: str  # Rewritten query without context dependence
    history_context: str  # Formatted conversation history


class LectureFollowupError(RuntimeError):
    """Raised when follow-up rewrite call fails."""


class LectureFollowupService(Protocol):
    """Interface for resolving follow-up questions with conversation context."""

    async def resolve_query(
        self,
        session_id: str,
        user_id: str,
        question: str,
        history_turns: int = 3,
    ) -> FollowupResolution:
        """Resolve follow-up question to standalone query using history."""
        ...


class SqlAlchemyLectureFollowupService:
    """Follow-up service using conversation history from QATurn."""

    DEFAULT_HISTORY_TURNS = 3
    DEFAULT_REWRITE_MODEL = "gpt-5-nano"
    DEFAULT_TIMEOUT_SECONDS = 20
    DEFAULT_API_VERSION = "2024-05-01-preview"

    def __init__(
        self,
        db: AsyncSession,
        openai_api_key: str = "",
        openai_endpoint: str = "",
        openai_account_name: str = "",
        model: str = DEFAULT_REWRITE_MODEL,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        api_version: str = DEFAULT_API_VERSION,
    ) -> None:
        """Initialize follow-up service.

        Args:
            db: Database session for loading history
            openai_api_key: Azure OpenAI API key (optional - if empty, uses simple rewrite)
            openai_endpoint: Azure OpenAI endpoint (optional)
            model: Model deployment name
            timeout_seconds: Request timeout
        """
        self._db = db
        self._openai_api_key = openai_api_key
        self._openai_endpoint = openai_endpoint
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._api_version = api_version
        self._last_usage: LLMUsage | None = None
        self._validation = self._validate_configuration(
            account_name=openai_account_name
        )
        if not self._validation.is_valid:
            logger.warning(
                "azure_openai_followup_config_invalid reason=%s",
                self._validation.reason,
            )

    async def resolve_query(
        self,
        session_id: str,
        user_id: str,
        question: str,
        history_turns: int = DEFAULT_HISTORY_TURNS,
    ) -> FollowupResolution:
        """Resolve follow-up question to standalone query.

        Args:
            session_id: Lecture session ID
            user_id: User ID for ownership validation
            question: Follow-up question (may contain pronouns/ellipsis)
            history_turns: Number of previous turns to include

        Returns:
            Resolution with standalone query and formatted history
        """
        # Load conversation history
        history = await self._load_history(
            session_id=session_id,
            user_id=user_id,
            turns=history_turns,
        )

        # Format history for prompt
        history_context = self._format_history(history)

        # Rewrite question to standalone
        standalone_query = await self._rewrite_to_standalone(
            question=question,
            history=history_context,
        )

        return FollowupResolution(
            standalone_query=standalone_query,
            history_context=history_context,
        )

    async def _load_history(
        self,
        session_id: str,
        user_id: str,
        turns: int,
    ) -> list[QATurn]:
        """Load recent QA turns for the session.

        Args:
            session_id: Lecture session ID
            user_id: User ID (for filtering - not used for lecture QA)
            turns: Maximum number of turns to load

        Returns:
            List of QA turns ordered by most recent first
        """
        result = await self._db.execute(
            select(QATurn)
            .join(LectureSession, LectureSession.id == QATurn.session_id)
            .where(
                QATurn.session_id == session_id,
                QATurn.feature == "lecture_qa",
                LectureSession.user_id == user_id,
            )
            .order_by(QATurn.created_at.desc())
            .limit(turns)
        )
        turns_list = list(result.scalars().all())
        # Reverse to chronological order
        return turns_list[::-1]

    def _format_history(self, history: list[QATurn]) -> str:
        """Format conversation history for prompt.

        Args:
            history: List of QA turns

        Returns:
            Formatted history string
        """
        if not history:
            return ""

        lines = ["会話履歴:"]
        for i, turn in enumerate(history, 1):
            lines.append(f"Q{i}: {turn.question}")
            lines.append(f"A{i}: {turn.answer}")
        return "\n".join(lines)

    async def _rewrite_to_standalone(
        self,
        question: str,
        history: str,
    ) -> str:
        """Rewrite follow-up question to standalone query.

        Args:
            question: Follow-up question (may have pronouns/ellipsis)
            history: Formatted conversation history

        Returns:
            Standalone query that can be understood without context
        """
        if not history:
            return question

        if not self._is_azure_openai_ready():
            return self._simple_rewrite(question, history)

        prompt = self._build_rewrite_prompt(question, history)
        try:
            rewritten = await self._call_openai_rewrite(prompt)
            if rewritten.strip():
                return rewritten.strip()
        except LectureFollowupError:
            logger.warning("lecture_followup_rewrite_failed_use_simple_rewrite")

        return self._simple_rewrite(question, history)

    def _simple_rewrite(self, question: str, history: str) -> str:
        """Simple heuristic-based rewrite without LLM.

        For Japanese common patterns:
        - "それは" -> prepend last subject
        - "どうして" -> prepend last topic
        """
        # If question starts with common pronouns, prepend context
        prefixes = ["それは", "それ", "その", "どうして", "なぜ"]
        lower_q = question.lower()

        for prefix in prefixes:
            if lower_q.startswith(prefix):
                # Extract last topic from history
                last_q = ""
                if "Q1:" in history:
                    # Extract first question as context
                    idx = history.index("Q1:") + 3
                    end_idx = history.find("\n", idx)
                    if end_idx != -1:
                        last_q = history[idx:end_idx].strip()

                if last_q:
                    # Combine context and question
                    return f"{last_q}に関して、{question}"

        return question

    def _build_rewrite_prompt(self, question: str, history: str) -> str:
        """Build LLM prompt for query rewrite."""
        if self._is_english_text(question):
            return f"""You rewrite context-dependent follow-up questions into standalone questions.

Given the conversation history and the latest question, rewrite the latest question so it can be understood without prior context.

[Conversation history]
{history}

[Latest question]
{question}

Requirements:
- Replace pronouns (for example, "it", "that", "this") with explicit nouns when possible
- Fill omitted subject/object based on the conversation context
- Keep the rewritten question in English
- Return only the rewritten question (no explanation)

Rewritten question:"""

        return f"""あなたは会話の文脈を理解して、質問を書き換えるアシスタントです。

以下の会話履歴と最新の質問を考慮して、最新の質問を独立した質問に書き換えてください。

【会話履歴】
{history}

【最新の質問】
{question}

タスク:
- 代名詞（それ、その等）を具体的な名詞に置き換えてください
- 省略された主語や目的語を補完してください
- 会話の文脈を考慮して、独立した質問にしてください
- 最新の質問と同じ言語で出力してください
- 書き換えた質問だけを出力してください（説明不要）

書き換えた質問:"""

    @staticmethod
    def _is_english_text(text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return False
        has_latin = bool(re.search(r"[A-Za-z]", stripped))
        has_japanese = bool(re.search(r"[ぁ-んァ-ン一-龥]", stripped))
        return has_latin and not has_japanese

    async def _call_openai_rewrite(self, prompt: str) -> str:
        """Call Azure OpenAI API for follow-up rewrite."""
        url = self._build_chat_completion_url()
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Rewrite follow-up questions into standalone questions "
                        "without adding external facts."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "max_completion_tokens": 256,
        }
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url=url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "api-key": self._openai_api_key,
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
            rewritten = self._extract_content(response_json).strip()
            return rewritten
        except HTTPError as exc:
            logger.warning(
                "azure_openai_followup_http_error status=%s",
                getattr(exc, "code", "unknown"),
            )
            raise LectureFollowupError(
                "azure openai follow-up rewrite request failed"
            ) from exc
        except URLError as exc:
            logger.warning("azure_openai_followup_network_error")
            raise LectureFollowupError(
                "azure openai follow-up rewrite network failure"
            ) from exc
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning("azure_openai_followup_parse_error")
            raise LectureFollowupError(
                "azure openai follow-up rewrite parse failure"
            ) from exc

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
            api_key=self._openai_api_key,
            endpoint=self._openai_endpoint,
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
