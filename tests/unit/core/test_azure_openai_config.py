"""Unit tests for shared Azure OpenAI configuration helpers."""

from app.core.azure_openai_config import (
    normalize_openai_endpoint,
    validate_openai_config,
)


def test_normalize_openai_endpoint_keeps_openai_host() -> None:
    endpoint = "https://sample.openai.azure.com/"
    result = normalize_openai_endpoint(endpoint, account_name="ignored")
    assert result == "https://sample.openai.azure.com"


def test_normalize_openai_endpoint_converts_cognitive_host() -> None:
    endpoint = "https://japaneast.api.cognitive.microsoft.com/"
    result = normalize_openai_endpoint(endpoint, account_name="aoai-test")
    assert result == "https://aoai-test.openai.azure.com"


def test_validate_openai_config_rejects_missing_deployment() -> None:
    result = validate_openai_config(
        api_key="key",
        endpoint="https://sample.openai.azure.com",
        deployment="",
    )
    assert result.is_valid is False
    assert result.reason == "missing_deployment"


def test_validate_openai_config_rejects_cognitive_host_without_account_name() -> None:
    result = validate_openai_config(
        api_key="key",
        endpoint="https://japaneast.api.cognitive.microsoft.com/",
        deployment="gpt-4o",
    )
    assert result.is_valid is False
    assert result.reason == "invalid_endpoint"
