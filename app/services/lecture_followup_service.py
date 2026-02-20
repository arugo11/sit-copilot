"""Lecture follow-up service for context-aware query resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.qa_turn import QATurn

__all__ = [
    "LectureFollowupService",
    "SqlAlchemyLectureFollowupService",
    "FollowupResolution",
]


@dataclass
class FollowupResolution:
    """Result of follow-up query resolution."""

    standalone_query: str  # Rewritten query without context dependence
    history_context: str  # Formatted conversation history


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
    DEFAULT_REWRITE_MODEL = "gpt-4o"
    DEFAULT_TIMEOUT_SECONDS = 20

    def __init__(
        self,
        db: AsyncSession,
        openai_api_key: str = "",
        openai_endpoint: str = "",
        model: str = DEFAULT_REWRITE_MODEL,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
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
            .where(
                QATurn.session_id == session_id,
                QATurn.feature == "lecture_qa",
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
            # No history - return as-is
            return question

        if not self._openai_api_key:
            # No OpenAI configured - use simple heuristic
            return self._simple_rewrite(question, history)

        # Use LLM for rewrite
        prompt = self._build_rewrite_prompt(question, history)
        return await self._call_openai_rewrite(prompt)

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
- 書き換えた質問だけを出力してください（説明不要）

書き換えた質問:"""

    async def _call_openai_rewrite(self, prompt: str) -> str:
        """Call Azure OpenAI API for query rewrite.

        Note: This is a placeholder implementation.
        Real implementation should use openai.AsyncAzureOpenAI.
        """
        # TODO: Implement real Azure OpenAI call
        # from openai import AsyncAzureOpenAI
        # client = AsyncAzureOpenAI(...)
        # response = await client.chat.completions.create(...)
        # return response.choices[0].message.content.strip()

        # Placeholder - return simple rewrite
        return self._simple_rewrite(prompt, "")
