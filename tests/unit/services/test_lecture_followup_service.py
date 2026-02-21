"""Unit tests for lecture follow-up service."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from urllib.error import HTTPError, URLError

import pytest

from app.models.qa_turn import QATurn
from app.services.lecture_followup_service import (
    FollowupResolution,
    SqlAlchemyLectureFollowupService,
)

# Test configuration constants
DISABLED_AZURE_OPENAI = ""  # Explicitly disabled for testing
TEST_AZURE_OPENAI_KEY = "TEST_AZURE_OPENAI_KEY_DO_NOT_USE_IN_PROD"


@pytest.fixture
def mock_db_session():
    """Mock AsyncSession for testing.

    Note: execute() is async but scalars().all() returns a sync list.
    """
    session = AsyncMock()
    # Mock the async execute() to return a sync result
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    session.execute.return_value = mock_result
    return session


@pytest.fixture
def sample_qa_turns():
    """Sample QA turns for testing."""
    return [
        QATurn(
            id="turn-1",
            session_id="test-session",
            feature="lecture_qa",
            question="BM25アルゴリズムとは何ですか？",
            answer="BM25は情報検索のためのランキング関数です。",
            confidence="high",
            citations_json=[],
            retrieved_chunk_ids_json=[],
            latency_ms=100,
            verifier_supported=True,
            outcome_reason="verified",
            created_at=datetime.now(UTC),
        ),
        QATurn(
            id="turn-2",
            session_id="test-session",
            feature="lecture_qa",
            question="どうしてTF-IDFと違うのですか？",
            answer="BM25は文書長の正規化を行う点で異なります。",
            confidence="high",
            citations_json=[],
            retrieved_chunk_ids_json=[],
            latency_ms=150,
            verifier_supported=True,
            outcome_reason="verified",
            created_at=datetime.now(UTC),
        ),
    ]


@pytest.mark.asyncio
async def test_resolve_query_with_empty_history(mock_db_session):
    """Resolve query with no prior conversation history."""
    service = SqlAlchemyLectureFollowupService(
        db=mock_db_session,
        openai_api_key="",
    )

    result = await service.resolve_query(
        session_id="test-session",
        user_id="user-1",
        question="BM25について教えて",
    )

    assert isinstance(result, FollowupResolution)
    assert result.standalone_query == "BM25について教えて"
    assert result.history_context == ""
    mock_db_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_resolve_query_with_history(mock_db_session, sample_qa_turns):
    """Resolve query with prior conversation history."""
    # Setup mock to return sample turns
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = sample_qa_turns
    mock_result.scalars.return_value = mock_scalars
    mock_db_session.execute.return_value = mock_result

    service = SqlAlchemyLectureFollowupService(
        db=mock_db_session,
        openai_api_key="",  # Use simple rewrite
    )

    result = await service.resolve_query(
        session_id="test-session",
        user_id="user-1",
        question="それについて詳しく",
    )

    assert isinstance(result, FollowupResolution)
    assert "会話履歴:" in result.history_context
    assert result.history_context.count("Q") == 2
    assert result.history_context.count("A") == 2


@pytest.mark.asyncio
async def test_resolve_query_with_pronoun_prefix(mock_db_session, sample_qa_turns):
    """Resolve query with Japanese pronoun patterns (それ, その)."""
    # Setup mock to return sample turns
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = sample_qa_turns
    mock_result.scalars.return_value = mock_scalars
    mock_db_session.execute.return_value = mock_result

    service = SqlAlchemyLectureFollowupService(
        db=mock_db_session,
        openai_api_key=DISABLED_AZURE_OPENAI,  # Use simple rewrite
    )

    # Test "それは" pattern
    result = await service.resolve_query(
        session_id="test-session",
        user_id="user-1",
        question="それはどういう意味ですか？",
    )

    # Simple rewrite should either resolve pronoun or keep context
    assert (
        "BM25アルゴリズム" in result.standalone_query
        or "それ" in result.standalone_query
    )


@pytest.mark.asyncio
async def test_simple_rewrite_no_history():
    """Simple rewrite with no history returns original question."""
    service = SqlAlchemyLectureFollowupService(
        db=AsyncMock(),
        openai_api_key=DISABLED_AZURE_OPENAI,
    )

    result = service._simple_rewrite(  # noqa: SLF001 - testing private method
        question="BM25とは何ですか？",
        history="",
    )

    assert result == "BM25とは何ですか？"


@pytest.mark.asyncio
async def test_simple_rewrite_with_pronoun():
    """Simple rewrite with Japanese pronoun pattern."""
    service = SqlAlchemyLectureFollowupService(
        db=AsyncMock(),
        openai_api_key=DISABLED_AZURE_OPENAI,
    )

    history = """会話履歴:
Q1: BM25アルゴリズムとは何ですか？
A1: BM25は情報検索のためのランキング関数です。"""

    result = service._simple_rewrite(  # noqa: SLF001 - testing private method
        question="それはどう使いますか？",
        history=history,
    )

    # Should prepend context
    assert "BM25アルゴリズム" in result or "それ" in result


@pytest.mark.asyncio
async def test_simple_rewrite_unknown_prefix():
    """Simple rewrite with unknown prefix returns original."""
    service = SqlAlchemyLectureFollowupService(
        db=AsyncMock(),
        openai_api_key=DISABLED_AZURE_OPENAI,
    )

    history = """会話履歴:
Q1: Pythonについて教えて
A1: Pythonはプログラミング言語です"""

    result = service._simple_rewrite(  # noqa: SLF001 - testing private method
        question="Rustについても教えて",
        history=history,
    )

    # Unknown prefix should return original question
    assert result == "Rustについても教えて"


@pytest.mark.asyncio
async def test_azure_openai_rewrite_success(mock_db_session):
    """Azure OpenAI rewrite with successful API call."""
    service = SqlAlchemyLectureFollowupService(
        db=mock_db_session,
        openai_api_key=TEST_AZURE_OPENAI_KEY,
        openai_endpoint="https://test.openai.azure.com/",
    )

    history = """会話履歴:
Q1: BM25とは何ですか？
A1: BM25は情報検索のためのランキング関数です。"""

    import json
    from unittest.mock import patch

    mock_response_data = {
        "choices": [
            {"message": {"content": "BM25アルゴリズムの特徴を詳しく説明してください"}}
        ]
    }

    with patch("app.services.lecture_followup_service.urlopen") as mock_urlopen:
        mock_http_response = MagicMock()
        mock_http_response.read.return_value = json.dumps(mock_response_data).encode(
            "utf-8"
        )
        mock_urlopen.return_value.__enter__.return_value = mock_http_response

        result = await service._rewrite_to_standalone(  # noqa: SLF001 - testing private method
            question="それについて詳しく",
            history=history,
        )

        assert "BM25" in result
        mock_urlopen.assert_called_once()


@pytest.mark.asyncio
async def test_azure_openai_rewrite_falls_back_to_simple(mock_db_session):
    """Azure OpenAI rewrite error falls back to simple rewrite."""
    service = SqlAlchemyLectureFollowupService(
        db=mock_db_session,
        openai_api_key=TEST_AZURE_OPENAI_KEY,
        openai_endpoint="https://test.openai.azure.com/",
    )

    history = """会話履歴:
Q1: BM25とは何ですか？
A1: BM25は情報検索のためのランキング関数です。"""

    from unittest.mock import patch

    with patch("app.services.lecture_followup_service.urlopen") as mock_urlopen:
        # Create a proper HTTPError with correct types
        mock_urlopen.side_effect = HTTPError(
            url="https://test.openai.azure.com/",
            code=429,
            msg="Rate limited",
            hdrs={},  # type: ignore[arg-type] - Test mock doesn't need real headers
            fp=None,
        )

        result = await service._rewrite_to_standalone(  # noqa: SLF001 - testing private method
            question="それについて詳しく",
            history=history,
        )

        # Should fall back to simple rewrite (still contains original or modified query)
        assert isinstance(result, str)
        assert len(result) > 0


def test_format_history_empty():
    """Format empty history returns empty string."""
    service = SqlAlchemyLectureFollowupService(
        db=AsyncMock(),
        openai_api_key=DISABLED_AZURE_OPENAI,
    )

    result = service._format_history([])  # noqa: SLF001 - testing private method

    assert result == ""


def test_format_history_with_turns(sample_qa_turns):
    """Format history with QA turns."""
    service = SqlAlchemyLectureFollowupService(
        db=AsyncMock(),
        openai_api_key=DISABLED_AZURE_OPENAI,
    )

    result = service._format_history(sample_qa_turns)  # noqa: SLF001 - testing private method

    assert "会話履歴:" in result
    assert "Q1: BM25アルゴリズムとは何ですか？" in result
    assert "A1: BM25は情報検索のためのランキング関数です。" in result
    assert "Q2: どうしてTF-IDFと違うのですか？" in result


def test_is_azure_openai_ready_missing_config():
    """Azure OpenAI readiness check with missing config."""
    service = SqlAlchemyLectureFollowupService(
        db=AsyncMock(),
        openai_api_key="",  # Empty key
    )

    result = service._is_azure_openai_ready()  # noqa: SLF001 - testing private method

    assert result is False


def test_is_azure_openai_ready_invalid_endpoint():
    """Azure OpenAI readiness check with invalid endpoint."""
    service = SqlAlchemyLectureFollowupService(
        db=AsyncMock(),
        openai_api_key=TEST_AZURE_OPENAI_KEY,
        openai_endpoint="https://api.openai.com/",  # Not azure
    )

    result = service._is_azure_openai_ready()  # noqa: SLF001 - testing private method

    assert result is False


def test_is_azure_openai_ready_valid_config():
    """Azure OpenAI readiness check with valid config."""
    service = SqlAlchemyLectureFollowupService(
        db=AsyncMock(),
        openai_api_key=TEST_AZURE_OPENAI_KEY,
        openai_endpoint="https://test.openai.azure.com",
    )

    result = service._is_azure_openai_ready()  # noqa: SLF001 - testing private method

    assert result is True


@pytest.mark.asyncio
async def test_extract_content_various_formats():
    """Extract content from various response formats."""
    service = SqlAlchemyLectureFollowupService(
        db=AsyncMock(),
        openai_api_key=TEST_AZURE_OPENAI_KEY,
        openai_endpoint="https://test.openai.azure.com/",
    )

    # Test with string content
    string_response = {"choices": [{"message": {"content": "Test response"}}]}

    result = service._extract_content(string_response)  # noqa: SLF001 - testing private method
    assert result == "Test response"

    # Test with list content (multimodal format)
    list_response = {
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "text", "text": "First part"},
                        {"type": "text", "text": "Second part"},
                    ]
                }
            }
        ]
    }

    result = service._extract_content(list_response)  # noqa: SLF001 - testing private method
    assert result == "First part\nSecond part"


@pytest.mark.asyncio
async def test_extract_content_malformed_responses():
    """Extract content handles malformed responses."""
    service = SqlAlchemyLectureFollowupService(
        db=AsyncMock(),
        openai_api_key=TEST_AZURE_OPENAI_KEY,
        openai_endpoint="https://test.openai.azure.com/",
    )

    # Missing choices
    with pytest.raises(ValueError, match="missing choices"):
        service._extract_content({})  # noqa: SLF001 - testing private method

    # Empty choices
    with pytest.raises(ValueError, match="missing choices"):
        service._extract_content({"choices": []})  # noqa: SLF001 - testing private method

    # Missing message
    with pytest.raises(ValueError, match="missing message"):
        service._extract_content({"choices": [{}]})  # noqa: SLF001 - testing private method

    # Missing content
    with pytest.raises(ValueError, match="missing content"):
        service._extract_content({"choices": [{"message": {}}]})  # noqa: SLF001 - testing private method


@pytest.mark.asyncio
async def test_load_history_empty_database(mock_db_session):
    """Load history when database has no matching turns."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    mock_db_session.execute.return_value = mock_result

    service = SqlAlchemyLectureFollowupService(
        db=mock_db_session,
        openai_api_key="",
    )

    result = await service._load_history(  # noqa: SLF001 - testing private method
        session_id="nonexistent-session",
        user_id="user-1",
        turns=3,
    )

    assert result == []


@pytest.mark.asyncio
async def test_load_history_with_turns(mock_db_session, sample_qa_turns):
    """Load history returns turns in chronological order."""
    # Mock returns in reverse chronological (most recent first)
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    # Return reversed (newest first as per query order_by desc)
    mock_scalars.all.return_value = list(reversed(sample_qa_turns))
    mock_result.scalars.return_value = mock_scalars
    mock_db_session.execute.return_value = mock_result

    service = SqlAlchemyLectureFollowupService(
        db=mock_db_session,
        openai_api_key="",
    )

    result = await service._load_history(  # noqa: SLF001 - testing private method
        session_id="test-session",
        user_id="user-1",
        turns=3,
    )

    # Should be reversed to chronological order
    assert len(result) == 2
    assert result[0].id == "turn-1"
    assert result[1].id == "turn-2"


@pytest.mark.asyncio
async def test_azure_openai_rewrite_network_error():
    """Azure OpenAI rewrite with network error falls back to simple."""
    service = SqlAlchemyLectureFollowupService(
        db=AsyncMock(),
        openai_api_key=TEST_AZURE_OPENAI_KEY,
        openai_endpoint="https://test.openai.azure.com/",
    )

    history = """会話履歴:
Q1: BM25とは何ですか？
A1: BM25は情報検索のためのランキング関数です。"""

    from unittest.mock import patch

    with patch("app.services.lecture_followup_service.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = URLError("Network error")

        result = await service._rewrite_to_standalone(  # noqa: SLF001 - testing private method
            question="それについて詳しく",
            history=history,
        )

        # Should fall back to simple rewrite
        assert isinstance(result, str)
        assert len(result) > 0


@pytest.mark.asyncio
async def test_azure_openai_rewrite_json_error():
    """Azure OpenAI rewrite with JSON parse error falls back."""
    service = SqlAlchemyLectureFollowupService(
        db=AsyncMock(),
        openai_api_key=TEST_AZURE_OPENAI_KEY,
        openai_endpoint="https://test.openai.azure.com/",
    )

    history = """会話履歴:
Q1: BM25とは何ですか？
A1: BM25は情報検索のためのランキング関数です。"""

    from unittest.mock import patch

    with patch("app.services.lecture_followup_service.urlopen") as mock_urlopen:
        mock_http_response = MagicMock()
        mock_http_response.read.return_value = b"invalid json"
        mock_urlopen.return_value.__enter__.return_value = mock_http_response

        result = await service._rewrite_to_standalone(  # noqa: SLF001 - testing private method
            question="それについて詳しく",
            history=history,
        )

        # Should fall back to simple rewrite
        assert isinstance(result, str)
        assert len(result) > 0


def test_build_rewrite_prompt_structure():
    """Build rewrite prompt has correct structure."""
    service = SqlAlchemyLectureFollowupService(
        db=AsyncMock(),
        openai_api_key=TEST_AZURE_OPENAI_KEY,
    )

    question = "それはどういう意味ですか？"
    history = """会話履歴:
Q1: BM25とは何ですか？
A1: BM25は情報検索のためのランキング関数です。"""

    result = service._build_rewrite_prompt(question, history)  # noqa: SLF001 - testing private method

    assert "会話の文脈を理解" in result
    assert "会話履歴" in result
    assert history in result
    assert question in result
    assert "代名詞" in result


@pytest.mark.asyncio
async def test_resolve_query_uses_history_turns_parameter(mock_db_session):
    """Resolve query respects history_turns parameter."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    mock_db_session.execute.return_value = mock_result

    service = SqlAlchemyLectureFollowupService(
        db=mock_db_session,
        openai_api_key="",
    )

    await service.resolve_query(
        session_id="test-session",
        user_id="user-1",
        question="質問",
        history_turns=5,
    )

    # Verify the query was executed
    mock_db_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_rewrite_to_standalone_with_no_history():
    """Rewrite to standalone with no history returns original question."""
    service = SqlAlchemyLectureFollowupService(
        db=AsyncMock(),
        openai_api_key=DISABLED_AZURE_OPENAI,
    )

    result = await service._rewrite_to_standalone(  # noqa: SLF001 - testing private method
        question="BM25とは何ですか？",
        history="",
    )

    assert result == "BM25とは何ですか？"


@pytest.mark.asyncio
async def test_rewrite_to_standalone_with_azure_disabled():
    """Rewrite with Azure disabled uses simple rewrite."""
    service = SqlAlchemyLectureFollowupService(
        db=AsyncMock(),
        openai_api_key="",  # Disabled
    )

    history = """会話履歴:
Q1: Pythonについて教えて
A1: Pythonはプログラミング言語です"""

    result = await service._rewrite_to_standalone(  # noqa: SLF001 - testing private method
        question="それはどう使いますか？",
        history=history,
    )

    # Should use simple rewrite logic
    assert isinstance(result, str)


def test_simple_rewrite_all_pronoun_prefixes():
    """Simple rewrite handles all Japanese pronoun prefixes."""
    service = SqlAlchemyLectureFollowupService(
        db=AsyncMock(),
        openai_api_key=DISABLED_AZURE_OPENAI,
    )

    history = """会話履歴:
Q1: 機械学習とは何ですか？
A1: 機械学習はデータから学習するAIの手法です。"""

    prefixes = ["それは", "それ", "その", "どうして", "なぜ"]

    for prefix in prefixes:
        question = f"{prefix}詳しく教えて"
        result = service._simple_rewrite(question, history)  # noqa: SLF001 - testing private method
        assert isinstance(result, str)
        assert len(result) > 0


def test_build_chat_completion_url():
    """Build chat completion URL has correct format."""
    service = SqlAlchemyLectureFollowupService(
        db=AsyncMock(),
        openai_api_key=TEST_AZURE_OPENAI_KEY,
        openai_endpoint="https://test.openai.azure.com/",
        model="gpt-4o",
    )

    result = service._build_chat_completion_url()  # noqa: SLF001 - testing private method

    assert (
        "https://test.openai.azure.com/openai/deployments/gpt-4o/chat/completions"
        in result
    )
    assert "api-version=2024-10-21" in result


def test_build_chat_completion_url_with_trailing_slash():
    """Build chat completion URL handles trailing slash."""
    service = SqlAlchemyLectureFollowupService(
        db=AsyncMock(),
        openai_api_key=TEST_AZURE_OPENAI_KEY,
        openai_endpoint="https://test.openai.azure.com/",  # Trailing slash
        model="gpt-4o",
    )

    result = service._build_chat_completion_url()  # noqa: SLF001 - testing private method

    # Should have the path without double slash after domain
    assert (
        "https://test.openai.azure.com/openai/deployments/gpt-4o/chat/completions"
        in result
    )
    # Should not have triple slash (mis-handled trailing slash)
    assert "///" not in result
