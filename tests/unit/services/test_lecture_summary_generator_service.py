"""Unit tests for lecture summary generator service."""

import json
from unittest.mock import MagicMock, Mock, patch
from urllib.error import HTTPError, URLError

import pytest

from app.models.speech_event import SpeechEvent
from app.models.visual_event import VisualEvent
from app.services.lecture_summary_generator_service import (
    AzureOpenAILectureSummaryGeneratorService,
    LectureSummaryGeneratorError,
    UnavailableLectureSummaryGeneratorService,
)

# ruff: noqa: ARG001 (unused mock arguments in pytest fixtures)


@pytest.fixture
def sample_speech_events() -> list[SpeechEvent]:
    """Sample speech events for testing."""
    event1 = SpeechEvent(
        id="speech_001",
        session_id="lec_001",
        start_ms=15000,
        end_ms=22000,
        text="外れ値の確認手順を説明します。",
        confidence=0.93,
        is_final=True,
        speaker="teacher",
    )
    event2 = SpeechEvent(
        id="speech_002",
        session_id="lec_001",
        start_ms=23000,
        end_ms=28000,
        text="散布図で外れ値を視覚的に確認します。",
        confidence=0.91,
        is_final=True,
        speaker="teacher",
    )
    return [event1, event2]


@pytest.fixture
def sample_visual_events() -> list[VisualEvent]:
    """Sample visual events for testing."""
    event1 = VisualEvent(
        id="visual_001",
        session_id="lec_001",
        timestamp_ms=18000,
        source="slide",
        ocr_text="外れ値, 残差確認",
        ocr_confidence=0.82,
        quality="good",
        change_score=0.44,
        blob_path=None,
    )
    event2 = VisualEvent(
        id="visual_002",
        session_id="lec_001",
        timestamp_ms=25000,
        source="board",
        ocr_text="1. データ確認 2. 散布図作成",
        ocr_confidence=0.78,
        quality="good",
        change_score=0.52,
        blob_path=None,
    )
    return [event1, event2]


@pytest.fixture
def mock_azure_response() -> dict:
    """Mock successful Azure OpenAI response."""
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "summary": "この区間では、外れ値の確認手順として、まず散布図で視覚的な確認を行う方法が説明されました。外れ値や残差の確認が重要であることが強調されています。",
                            "key_terms": [
                                "外れ値",
                                "散布図",
                                "残差確認",
                                "データ確認",
                            ],
                            "evidence": [
                                {
                                    "type": "speech",
                                    "timestamp": "00:15",
                                    "text": "外れ値の確認手順を説明します。",
                                },
                                {
                                    "type": "slide",
                                    "timestamp": "00:18",
                                    "text": "外れ値, 残差確認",
                                },
                            ],
                        }
                    )
                }
            }
        ]
    }


# Helper function to create mock response
def _create_mock_http_response(response_data: dict | str) -> MagicMock:
    """Create a mock HTTP response that returns the given data."""
    mock_response = MagicMock()
    if isinstance(response_data, dict):
        mock_response.read.return_value = json.dumps(response_data).encode("utf-8")
    else:
        mock_response.read.return_value = response_data.encode("utf-8")
    return mock_response


@pytest.mark.asyncio
@patch("app.services.lecture_summary_generator_service.urlopen")
async def test_generate_summary_returns_valid_result(
    mock_urlopen: Mock,
    sample_speech_events: list[SpeechEvent],
    sample_visual_events: list[VisualEvent],
    mock_azure_response: dict,
) -> None:
    """Azure OpenAI returns valid summary with evidence."""
    # Arrange
    mock_urlopen.return_value.__enter__.return_value = _create_mock_http_response(
        mock_azure_response
    )

    service = AzureOpenAILectureSummaryGeneratorService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
        model="gpt-4o",
    )

    # Act
    result = await service.generate_summary(
        speech_events=sample_speech_events,
        visual_events=sample_visual_events,
        lang_mode="ja",
    )

    # Assert
    assert (
        result.summary
        == "この区間では、外れ値の確認手順として、まず散布図で視覚的な確認を行う方法が説明されました。外れ値や残差の確認が重要であることが強調されています。"
    )
    assert len(result.key_terms) == 4
    # key_terms is now a list of dicts with term, explanation, translation
    term_values = [
        term["term"] if isinstance(term, dict) else term for term in result.key_terms
    ]
    assert "外れ値" in term_values
    assert "散布図" in term_values
    assert len(result.evidence_tags) == 2
    assert result.evidence_tags[0]["type"] == "speech"
    assert result.evidence_tags[1]["type"] == "slide"


@pytest.mark.asyncio
@patch("app.services.lecture_summary_generator_service.urlopen")
async def test_generate_summary_with_invalid_json_raises_error(
    mock_urlopen: Mock,
    sample_speech_events: list[SpeechEvent],
    sample_visual_events: list[VisualEvent],
) -> None:
    """Invalid JSON response raises LectureSummaryGeneratorError."""
    # Arrange
    mock_urlopen.return_value.__enter__.return_value = _create_mock_http_response(
        "invalid json{{"
    )

    service = AzureOpenAILectureSummaryGeneratorService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    # Act & Assert
    with pytest.raises(LectureSummaryGeneratorError) as exc_info:
        await service.generate_summary(
            speech_events=sample_speech_events,
            visual_events=sample_visual_events,
            lang_mode="ja",
        )

    assert "parse failure" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_generate_summary_with_empty_api_key_raises_error(
    sample_speech_events: list[SpeechEvent],
    sample_visual_events: list[VisualEvent],
) -> None:
    """Empty api_key raises LectureSummaryGeneratorError."""
    # Arrange
    service = AzureOpenAILectureSummaryGeneratorService(
        api_key="",
        endpoint="https://test.openai.azure.com/",
    )

    # Act & Assert
    with pytest.raises(LectureSummaryGeneratorError) as exc_info:
        await service.generate_summary(
            speech_events=sample_speech_events,
            visual_events=sample_visual_events,
            lang_mode="ja",
        )

    assert "not configured" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_unavailable_generator_returns_fallback_summary_and_empty_keyterms(
    sample_speech_events: list[SpeechEvent],
    sample_visual_events: list[VisualEvent],
) -> None:
    """Unavailable generator should return fallback summary and no key terms."""
    service = UnavailableLectureSummaryGeneratorService(
        reason="azure openai summary backend is unavailable"
    )

    result = await service.generate_summary(
        speech_events=sample_speech_events,
        visual_events=sample_visual_events,
        lang_mode="ja",
    )

    assert result.summary != ""
    assert result.key_terms == []


@pytest.mark.asyncio
@patch("app.services.lecture_summary_generator_service.urlopen")
async def test_generate_summary_with_invalid_evidence_tag_is_skipped(
    mock_urlopen: Mock,
    sample_speech_events: list[SpeechEvent],
    sample_visual_events: list[VisualEvent],
) -> None:
    """Invalid evidence tag in response is skipped, not raised as error."""
    # Arrange
    response_with_invalid_tag = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "summary": "テスト要約",
                            "key_terms": ["テスト"],
                            "evidence": [
                                {
                                    "type": "speech",
                                    "timestamp": "00:15",
                                    "text": "テスト",
                                },
                                {
                                    "type": "invalid_type",  # Invalid tag
                                    "timestamp": "00:20",
                                    "text": "無効",
                                },
                                {
                                    "type": "slide",
                                    "timestamp": "00:18",
                                    "text": "スライド",
                                },
                            ],
                        }
                    )
                }
            }
        ]
    }

    mock_urlopen.return_value.__enter__.return_value = _create_mock_http_response(
        response_with_invalid_tag
    )

    service = AzureOpenAILectureSummaryGeneratorService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    # Act
    result = await service.generate_summary(
        speech_events=sample_speech_events,
        visual_events=sample_visual_events,
        lang_mode="ja",
    )

    # Assert - invalid tag should be skipped, only valid tags remain
    assert len(result.evidence_tags) == 2
    assert result.evidence_tags[0]["type"] == "speech"
    assert result.evidence_tags[1]["type"] == "slide"


@pytest.mark.asyncio
@patch("app.services.lecture_summary_generator_service.urlopen")
async def test_generate_summary_with_http_error_raises_error(
    mock_urlopen: Mock,
    sample_speech_events: list[SpeechEvent],
    sample_visual_events: list[VisualEvent],
) -> None:
    """HTTPError from Azure OpenAI raises LectureSummaryGeneratorError."""
    # Arrange
    mock_urlopen.side_effect = HTTPError("url", 500, "Internal Server Error", {}, None)

    service = AzureOpenAILectureSummaryGeneratorService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    # Act & Assert
    with pytest.raises(LectureSummaryGeneratorError) as exc_info:
        await service.generate_summary(
            speech_events=sample_speech_events,
            visual_events=sample_visual_events,
            lang_mode="ja",
        )

    assert "request failed" in str(exc_info.value).lower()


@pytest.mark.asyncio
@patch("app.services.lecture_summary_generator_service.urlopen")
async def test_generate_summary_with_network_error_raises_error(
    mock_urlopen: Mock,
    sample_speech_events: list[SpeechEvent],
    sample_visual_events: list[VisualEvent],
) -> None:
    """URLError from Azure OpenAI raises LectureSummaryGeneratorError."""
    # Arrange
    mock_urlopen.side_effect = URLError("network error")

    service = AzureOpenAILectureSummaryGeneratorService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    # Act & Assert
    with pytest.raises(LectureSummaryGeneratorError) as exc_info:
        await service.generate_summary(
            speech_events=sample_speech_events,
            visual_events=sample_visual_events,
            lang_mode="ja",
        )

    assert "network failure" in str(exc_info.value).lower()


@pytest.mark.asyncio
@patch("app.services.lecture_summary_generator_service.urlopen")
async def test_generate_summary_enforces_600_char_limit(
    mock_urlopen: Mock,
    sample_speech_events: list[SpeechEvent],
    sample_visual_events: list[VisualEvent],
) -> None:
    """Summary longer than 600 chars is truncated."""
    # Arrange
    long_summary = "あ" * 700  # 700 chars

    response_with_long_summary = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "summary": long_summary,
                            "key_terms": ["テスト"],
                            "evidence": [],
                        }
                    )
                }
            }
        ]
    }

    mock_urlopen.return_value.__enter__.return_value = _create_mock_http_response(
        response_with_long_summary
    )

    service = AzureOpenAILectureSummaryGeneratorService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    # Act
    result = await service.generate_summary(
        speech_events=sample_speech_events,
        visual_events=sample_visual_events,
        lang_mode="ja",
    )

    # Assert
    assert len(result.summary) == 600
    assert result.summary == "あ" * 600


@pytest.mark.asyncio
@patch("app.services.lecture_summary_generator_service.urlopen")
async def test_generate_summary_with_easy_ja_mode(
    mock_urlopen: Mock,
    sample_speech_events: list[SpeechEvent],
    sample_visual_events: list[VisualEvent],
) -> None:
    """Summary with easy-ja mode returns valid summary."""
    # Arrange
    response_easy_ja = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "summary": "やさしいにほんごでのようやくです。",
                            "key_terms": ["テスト"],
                            "evidence": [],
                        }
                    )
                }
            }
        ]
    }

    mock_urlopen.return_value.__enter__.return_value = _create_mock_http_response(
        response_easy_ja
    )

    service = AzureOpenAILectureSummaryGeneratorService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    # Act
    result = await service.generate_summary(
        speech_events=sample_speech_events,
        visual_events=sample_visual_events,
        lang_mode="easy-ja",
    )

    # Assert
    assert result.summary == "やさしいにほんごでのようやくです。"


@pytest.mark.asyncio
@patch("app.services.lecture_summary_generator_service.urlopen")
async def test_generate_summary_with_en_mode(
    mock_urlopen: Mock,
    sample_speech_events: list[SpeechEvent],
    sample_visual_events: list[VisualEvent],
) -> None:
    """Summary with en mode returns valid summary."""
    # Arrange
    response_en = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "summary": "This segment explains how to detect outliers.",
                            "key_terms": ["outlier", "scatter plot"],
                            "evidence": [],
                        }
                    )
                }
            }
        ]
    }

    mock_urlopen.return_value.__enter__.return_value = _create_mock_http_response(
        response_en
    )

    service = AzureOpenAILectureSummaryGeneratorService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    # Act
    result = await service.generate_summary(
        speech_events=sample_speech_events,
        visual_events=sample_visual_events,
        lang_mode="en",
    )

    # Assert
    assert result.summary == "This segment explains how to detect outliers."
    # key_terms is now a list of dicts with term, explanation, translation
    assert len(result.key_terms) == 2
    term_values = [
        term["term"] if isinstance(term, dict) else term for term in result.key_terms
    ]
    assert "outlier" in term_values
    assert "scatter plot" in term_values


@pytest.mark.asyncio
@patch("app.services.lecture_summary_generator_service.urlopen")
async def test_generate_summary_with_empty_events(
    mock_urlopen: Mock,
) -> None:
    """Summary generation handles empty speech and visual events."""
    # Arrange
    response_for_empty = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "summary": "この区間に講義コンテンツはありません。",
                            "key_terms": [],
                            "evidence": [],
                        }
                    )
                }
            }
        ]
    }

    mock_urlopen.return_value.__enter__.return_value = _create_mock_http_response(
        response_for_empty
    )

    service = AzureOpenAILectureSummaryGeneratorService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    # Act
    result = await service.generate_summary(
        speech_events=[],
        visual_events=[],
        lang_mode="ja",
    )

    # Assert
    assert result.summary == "この区間に講義コンテンツはありません。"
    assert result.key_terms == []
    assert result.evidence_tags == []


@pytest.mark.asyncio
async def test_generate_summary_with_non_azure_endpoint_raises_error(
    sample_speech_events: list[SpeechEvent],
    sample_visual_events: list[VisualEvent],
) -> None:
    """Non-Azure OpenAI endpoint raises LectureSummaryGeneratorError."""
    # Arrange
    service = AzureOpenAILectureSummaryGeneratorService(
        api_key="test-key",
        endpoint="https://api.openai.com/",  # Not openai.azure.com
    )

    # Act & Assert
    with pytest.raises(LectureSummaryGeneratorError) as exc_info:
        await service.generate_summary(
            speech_events=sample_speech_events,
            visual_events=sample_visual_events,
            lang_mode="ja",
        )

    assert "not configured" in str(exc_info.value).lower()


def test_is_azure_openai_ready_with_missing_deployment() -> None:
    """Missing deployment should disable Azure OpenAI runtime calls."""
    service = AzureOpenAILectureSummaryGeneratorService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
        model="",
    )

    assert service._is_azure_openai_ready() is False  # noqa: SLF001


def test_build_chat_completion_url_normalizes_cognitive_endpoint() -> None:
    """Cognitive endpoint should normalize using account name."""
    service = AzureOpenAILectureSummaryGeneratorService(
        api_key="test-key",
        endpoint="https://japaneast.api.cognitive.microsoft.com/",
        account_name="aoai-test",
        model="gpt-4o",
    )

    result = service._build_chat_completion_url()  # noqa: SLF001

    assert (
        "https://aoai-test.openai.azure.com/openai/deployments/gpt-4o/chat/completions"
        in result
    )
