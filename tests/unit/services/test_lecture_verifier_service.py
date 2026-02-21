"""Unit tests for lecture verifier service."""

from app.services.lecture_verifier_service import AzureOpenAILectureVerifierService


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
