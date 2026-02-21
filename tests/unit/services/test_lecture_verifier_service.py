"""Unit tests for lecture verifier service."""

from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

import pytest

from app.schemas.lecture_qa import LectureSource
from app.services.lecture_verifier_service import (
    AzureOpenAILectureVerifierService,
)

# =============================================================================
# Helper function to create valid LectureSource for testing
# =============================================================================


def _make_source(text: str, timestamp: str = "10:00") -> LectureSource:
    """Create a valid LectureSource for testing."""
    return LectureSource(
        chunk_id="test-chunk",
        type="speech",
        text=text,
        timestamp=timestamp,
        bm25_score=0.9,
    )


# =============================================================================
# Existing tests (parser behavior)
# =============================================================================


def test_parse_verification_result_handles_string_false_as_false() -> None:
    """String 'false' must not be treated as truthy pass."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    result = service._parse_verification_result(  # noqa: SLF001 - parser behavior test
        '{"passed":"false","summary":"検証失敗","unsupported_claims":[]}',
        answer="回答",
    )

    assert result.passed is False
    assert result.summary == "検証失敗"


def test_parse_verification_result_rejects_non_boolean_passed() -> None:
    """Invalid passed type should fail closed via parse error handling."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    result = service._parse_verification_result(  # noqa: SLF001 - parser behavior test
        '{"passed":1,"summary":"検証","unsupported_claims":[]}',
        answer="回答",
    )

    assert result.passed is False
    assert result.summary == "検証結果の解析に失敗しました。"
    assert result.unsupported_claims == ["回答"]


# =============================================================================
# Edge case: No sources
# =============================================================================


async def test_verify_with_no_sources() -> None:
    """Empty sources should return deterministic failure result."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    result = await service.verify(
        question="テスト質問",
        answer="テスト回答",
        sources=[],
    )

    assert result.passed is False
    assert result.summary == "検証用のソースがありません。"
    assert result.unsupported_claims == ["テスト回答"]


# =============================================================================
# Azure OpenAI success scenarios
# =============================================================================


async def test_verify_with_azure_openai_success() -> None:
    """Successful Azure OpenAI verification should return parsed result."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    mock_response = Mock()
    mock_response.read.return_value = (
        r'{"choices":[{"message":{"content":"{\"passed\": true, \"summary\": \"検証成功\", \"unsupported_claims\": []}"}}]}'
    ).encode()

    with patch("app.services.lecture_verifier_service.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = await service.verify(
            question="テスト質問",
            answer="テスト回答",
            sources=[_make_source("講義資料の内容")],
        )

        assert result.passed is True
        assert result.summary == "検証成功"
        assert result.unsupported_claims == []


async def test_verify_with_azure_openai_fails_verification() -> None:
    """Azure OpenAI verification that fails should return failed result."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    mock_response = Mock()
    mock_response.read.return_value = (
        r'{"choices":[{"message":{"content":"{\"passed\": false, \"summary\": \"根拠なし\", \"unsupported_claims\": [\"不明な主張\"]}"}}]}'
    ).encode()

    with patch("app.services.lecture_verifier_service.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = await service.verify(
            question="テスト質問",
            answer="テスト回答",
            sources=[_make_source("講義資料")],
        )

        assert result.passed is False
        assert result.summary == "根拠なし"
        assert result.unsupported_claims == ["不明な主張"]


# =============================================================================
# HTTP error handling
# =============================================================================


async def test_verify_with_http_error_429() -> None:
    """HTTPError with 429 status should raise LectureVerifierError."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    with patch("app.services.lecture_verifier_service.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = HTTPError(
            url="https://test.openai.azure.com/",
            code=429,
            msg="Rate limited",
            hdrs={},  # type: ignore[arg-type]
            fp=None,
        )

        from app.services.lecture_verifier_service import LectureVerifierError

        with pytest.raises(
            LectureVerifierError, match="azure openai verify request failed"
        ):
            await service.verify(
                question="テスト質問",
                answer="テスト回答",
                sources=[_make_source("資料")],
            )


async def test_verify_with_http_error_500() -> None:
    """HTTPError with 500 status should raise LectureVerifierError."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    with patch("app.services.lecture_verifier_service.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = HTTPError(
            url="https://test.openai.azure.com/",
            code=500,
            msg="Internal Server Error",
            hdrs={},  # type: ignore[arg-type]
            fp=None,
        )

        from app.services.lecture_verifier_service import LectureVerifierError

        with pytest.raises(
            LectureVerifierError, match="azure openai verify request failed"
        ):
            await service.verify(
                question="テスト質問",
                answer="テスト回答",
                sources=[_make_source("資料")],
            )


# =============================================================================
# Network error handling
# =============================================================================


async def test_verify_with_network_error() -> None:
    """URLError should raise LectureVerifierError with network message."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    with patch("app.services.lecture_verifier_service.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = URLError("Network unreachable")

        from app.services.lecture_verifier_service import LectureVerifierError

        with pytest.raises(
            LectureVerifierError, match="azure openai verify network failure"
        ):
            await service.verify(
                question="テスト質問",
                answer="テスト回答",
                sources=[_make_source("資料")],
            )


# =============================================================================
# Local fallback tests (empty api_key/endpoint)
# =============================================================================


async def test_local_verify_with_matching_content() -> None:
    """Local fallback should pass when answer contains source content."""
    service = AzureOpenAILectureVerifierService(
        api_key="",  # Empty triggers local fallback
        endpoint="",
    )

    result = await service.verify(
        question="テスト質問",
        answer="これは講義で説明された重要な概念です",
        sources=[_make_source("講義で説明された重要な概念")],
    )

    assert result.passed is True
    assert result.summary == "ローカル検証で根拠との一致を確認しました。"
    assert result.unsupported_claims == []


async def test_local_verify_with_no_match() -> None:
    """Local fallback should fail when answer doesn't contain source content."""
    service = AzureOpenAILectureVerifierService(
        api_key="",  # Empty triggers local fallback
        endpoint="",
    )

    result = await service.verify(
        question="テスト質問",
        answer="これはまったく関係のない回答です",
        sources=[_make_source("講義の実際の内容とは異なります")],
    )

    assert result.passed is False
    assert result.summary == "ローカル検証で根拠一致を確認できませんでした。"
    assert result.unsupported_claims == ["これはまったく関係のない回答です"]


async def test_local_verify_with_empty_answer() -> None:
    """Local fallback should fail with empty answer."""
    service = AzureOpenAILectureVerifierService(
        api_key="",
        endpoint="",
    )

    result = await service.verify(
        question="テスト質問",
        answer="   ",
        sources=[_make_source("講義資料")],
    )

    assert result.passed is False
    assert result.summary == "回答が空のため検証に失敗しました。"


# =============================================================================
# Repair answer tests
# =============================================================================


async def test_repair_answer_with_sources() -> None:
    """Repair should return repaired answer from Azure OpenAI."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    mock_response = Mock()
    mock_response.read.return_value = (
        '{"choices":[{"message":{"content":"修正された回答内容"}}]}'
    ).encode()

    with patch("app.services.lecture_verifier_service.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = await service.repair_answer(
            question="テスト質問",
            answer="元の回答",
            sources=[_make_source("講義資料")],
            unsupported_claims=["不明な主張"],
        )

        assert result == "修正された回答内容"


async def test_repair_answer_returns_none_on_impossible() -> None:
    """Repair should return None when Azure OpenAI returns '修正不可能'."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    mock_response = Mock()
    mock_response.read.return_value = (
        '{"choices":[{"message":{"content":"修正不可能"}}]}'
    ).encode()

    with patch("app.services.lecture_verifier_service.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = await service.repair_answer(
            question="テスト質問",
            answer="元の回答",
            sources=[_make_source("講義資料")],
            unsupported_claims=["不明な主張"],
        )

        assert result is None


async def test_repair_answer_with_empty_response() -> None:
    """Repair should return None when Azure OpenAI returns empty content."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    mock_response = Mock()
    mock_response.read.return_value = b'{"choices":[{"message":{"content":"   "}}]}'

    with patch("app.services.lecture_verifier_service.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = await service.repair_answer(
            question="テスト質問",
            answer="元の回答",
            sources=[_make_source("講義資料")],
            unsupported_claims=["不明な主張"],
        )

        assert result is None


async def test_repair_answer_with_no_sources() -> None:
    """Repair should return None when sources list is empty."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    result = await service.repair_answer(
        question="テスト質問",
        answer="元の回答",
        sources=[],
        unsupported_claims=["不明な主張"],
    )

    assert result is None


async def test_repair_answer_local_fallback_with_sources() -> None:
    """Local repair should return snippet from sources."""
    service = AzureOpenAILectureVerifierService(
        api_key="",  # Empty triggers local fallback
        endpoint="",
    )

    result = await service.repair_answer(
        question="テスト質問",
        answer="元の回答",
        sources=[_make_source("これは講義資料からの抜粋です")],
        unsupported_claims=["不明な主張"],
    )

    assert result is not None
    assert "講義資料からの抜粋" in result


async def test_repair_answer_http_error() -> None:
    """Repair should raise LectureVerifierError on HTTPError."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    with patch("app.services.lecture_verifier_service.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = HTTPError(
            url="https://test.openai.azure.com/",
            code=500,
            msg="Internal Server Error",
            hdrs={},  # type: ignore[arg-type]
            fp=None,
        )

        from app.services.lecture_verifier_service import LectureVerifierError

        with pytest.raises(
            LectureVerifierError, match="azure openai repair request failed"
        ):
            await service.repair_answer(
                question="テスト質問",
                answer="元の回答",
                sources=[_make_source("講義資料")],
                unsupported_claims=["不明な主張"],
            )


# =============================================================================
# Content extraction tests
# =============================================================================


async def test_extract_content_from_list_format() -> None:
    """Extract content when Azure OpenAI returns content as list (multimodal)."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    mock_response = Mock()
    # Azure OpenAI may return content as a list for multimodal responses
    mock_response.read.return_value = (
        r"""{"choices":[{"message":{"content":[{"type":"text","text":"検証結果のテキスト"}]}}]}"""
    ).encode()

    with patch("app.services.lecture_verifier_service.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = await service.verify(
            question="テスト質問",
            answer="テスト回答",
            sources=[_make_source("講義資料")],
        )

        # Should parse without error (content extraction handles list format)
        assert result is not None


async def test_extract_content_from_string_format() -> None:
    """Extract content when Azure OpenAI returns content as string."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    mock_response = Mock()
    mock_response.read.return_value = rb'{"choices":[{"message":{"content":"{\"passed\": true, \"summary\": \"OK\", \"unsupported_claims\": []}"}}]}'

    with patch("app.services.lecture_verifier_service.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = await service.verify(
            question="テスト質問",
            answer="テスト回答",
            sources=[_make_source("講義資料")],
        )

        assert result.passed is True
        assert result.summary == "OK"


# =============================================================================
# Malformed JSON handling
# =============================================================================


async def test_parse_verification_result_malformed_json() -> None:
    """Malformed JSON from Azure OpenAI should return safe default."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    mock_response = Mock()
    mock_response.read.return_value = (
        b'{"choices":[{"message":{"content":"invalid json content"}}]}'
    )

    with patch("app.services.lecture_verifier_service.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = await service.verify(
            question="テスト質問",
            answer="テスト回答",
            sources=[_make_source("講義資料")],
        )

        assert result.passed is False
        assert result.summary == "検証結果の解析に失敗しました。"
        assert result.unsupported_claims == ["テスト回答"]


async def test_parse_verification_result_empty_json() -> None:
    """Empty JSON object should return safe default."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    mock_response = Mock()
    mock_response.read.return_value = b'{"choices":[{"message":{"content":"{}"}}]}'

    with patch("app.services.lecture_verifier_service.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = await service.verify(
            question="テスト質問",
            answer="テスト回答",
            sources=[_make_source("講義資料")],
        )

        assert result.passed is True  # defaults to True when passed is missing
        assert result.summary == "検証が完了しました。"


# =============================================================================
# Helper method tests
# =============================================================================


def test_normalize_unsupported_claims_filters_non_strings() -> None:
    """Non-string items should be filtered from unsupported_claims."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    result = service._normalize_unsupported_claims(  # noqa: SLF001
        ["valid claim", 123, None, {"nested": "dict"}, "  another claim  "]
    )

    assert result == ["valid claim", "another claim"]


def test_normalize_unsupported_claims_with_empty_list() -> None:
    """Empty list should return empty list."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    result = service._normalize_unsupported_claims([])  # noqa: SLF001

    assert result == []


def test_normalize_unsupported_claims_with_non_list() -> None:
    """Non-list input should return empty list."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    result = service._normalize_unsupported_claims("not a list")  # noqa: SLF001

    assert result == []


def test_parse_passed_flag_with_boolean_true() -> None:
    """Boolean true should return true."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    result = service._parse_passed_flag(True)  # noqa: SLF001

    assert result is True


def test_parse_passed_flag_with_boolean_false() -> None:
    """Boolean false should return false."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    result = service._parse_passed_flag(False)  # noqa: SLF001

    assert result is False


def test_parse_passed_flag_with_string_true() -> None:
    """String 'true' should return true."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    result = service._parse_passed_flag("true")  # noqa: SLF001

    assert result is True


def test_parse_passed_flag_with_string_false() -> None:
    """String 'false' should return false."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    result = service._parse_passed_flag("false")  # noqa: SLF001

    assert result is False


def test_parse_passed_flag_with_invalid_type() -> None:
    """Non-boolean, non-string value should raise ValueError."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    with pytest.raises(ValueError, match="passed must be a boolean value"):
        service._parse_passed_flag(123)  # noqa: SLF001


def test_is_azure_openai_ready_with_missing_api_key() -> None:
    """Empty api_key should return false."""
    service = AzureOpenAILectureVerifierService(
        api_key="",
        endpoint="https://test.openai.azure.com/",
    )

    assert service._is_azure_openai_ready() is False  # noqa: SLF001


def test_is_azure_openai_ready_with_missing_endpoint() -> None:
    """Empty endpoint should return false."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="",
    )

    assert service._is_azure_openai_ready() is False  # noqa: SLF001


def test_is_azure_openai_ready_with_invalid_endpoint() -> None:
    """Non-Azure endpoint should return false."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://api.openai.com/",
    )

    assert service._is_azure_openai_ready() is False  # noqa: SLF001


def test_contains_source_fragment_with_exact_match() -> None:
    """Fragment matching should detect overlapping content when answer directly contains source text."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    result = service._contains_source_fragment(  # noqa: SLF001
        answer_text="これは講義の内容ですとても重要",
        source_text="講義の内容です",
    )

    assert result is True


def test_contains_source_fragment_with_no_match() -> None:
    """No fragment match should return false."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    result = service._contains_source_fragment(  # noqa: SLF001
        answer_text="完全に異なる内容です",
        source_text="これもまた別の内容になります",
    )

    assert result is False


def test_contains_source_fragment_with_empty_source() -> None:
    """Empty source text should return false."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    result = service._contains_source_fragment(  # noqa: SLF001
        answer_text="何かしらの内容",
        source_text="",
    )

    assert result is False


def test_normalize_text_removes_whitespace_and_lowercases() -> None:
    """Text normalization should remove whitespace and lowercase."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    result = service._normalize_text("  Hello   World  TEST  ")  # noqa: SLF001

    assert result == "helloworldtest"


# =============================================================================
# Additional edge case tests
# =============================================================================


async def test_verify_with_passed_true_but_unsupported_claims() -> None:
    """Verification with passed=true but unsupported_claims populated should fail."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    mock_response = Mock()
    mock_response.read.return_value = (
        r'{"choices":[{"message":{"content":"{\"passed\": true, \"summary\": \"矛盾した結果\", \"unsupported_claims\": [\"unsupported claim\"]}"}}]}'
    ).encode()

    with patch("app.services.lecture_verifier_service.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = await service.verify(
            question="テスト質問",
            answer="テスト回答",
            sources=[_make_source("講義資料")],
        )

        # Should fail closed when passed=True but unsupported_claims is non-empty
        assert result.passed is False
        assert result.unsupported_claims == ["unsupported claim"]


async def test_local_repair_answer_with_empty_source() -> None:
    """Local repair should return None when source text is empty."""
    service = AzureOpenAILectureVerifierService(
        api_key="",
        endpoint="",
    )

    result = await service.repair_answer(
        question="テスト質問",
        answer="元の回答",
        sources=[_make_source("   ")],
        unsupported_claims=["不明な主張"],
    )

    assert result is None


async def test_local_repair_answer_with_newline_in_source() -> None:
    """Local repair should convert newlines to spaces."""
    service = AzureOpenAILectureVerifierService(
        api_key="",
        endpoint="",
    )

    result = await service.repair_answer(
        question="テスト質問",
        answer="元の回答",
        sources=[_make_source("講義資料\nです\nこれは")],
        unsupported_claims=["不明な主張"],
    )

    assert result is not None
    assert "\n" not in result  # Newlines should be replaced with spaces


# =============================================================================
# Repair network error
# =============================================================================


async def test_repair_answer_with_network_error() -> None:
    """Repair should raise LectureVerifierError on network error."""
    service = AzureOpenAILectureVerifierService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
    )

    with patch("app.services.lecture_verifier_service.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = URLError("Network unreachable")

        from app.services.lecture_verifier_service import LectureVerifierError

        with pytest.raises(
            LectureVerifierError, match="azure openai repair network failure"
        ):
            await service.repair_answer(
                question="テスト質問",
                answer="元の回答",
                sources=[_make_source("講義資料")],
                unsupported_claims=["不明な主張"],
            )


