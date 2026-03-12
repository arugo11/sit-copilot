"""Shared Azure OpenAI endpoint normalization and validation."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

SUPPORTED_AZURE_OPENAI_HOST_SUFFIXES = (
    ".openai.azure.com",
    ".api.cognitive.microsoft.com",
    ".cognitiveservices.azure.com",
)


@dataclass(frozen=True)
class ValidationResult:
    """Validation outcome for Azure OpenAI runtime settings."""

    is_valid: bool
    normalized_endpoint: str
    reason: str


def normalize_openai_endpoint(endpoint: str, account_name: str = "") -> str:
    """Normalize endpoint while preserving reachable Azure OpenAI hosts."""
    normalized_endpoint = endpoint.strip().rstrip("/")
    if not normalized_endpoint:
        return ""

    parsed = urlparse(normalized_endpoint)
    host = parsed.netloc.lower()
    if not host:
        return normalized_endpoint

    if host.endswith(SUPPORTED_AZURE_OPENAI_HOST_SUFFIXES):
        return normalized_endpoint

    return normalized_endpoint


def validate_openai_config(
    *,
    api_key: str,
    endpoint: str,
    deployment: str,
    account_name: str = "",
) -> ValidationResult:
    """Validate runtime settings required by Azure OpenAI chat completions."""
    if not api_key.strip():
        return ValidationResult(
            is_valid=False,
            normalized_endpoint="",
            reason="missing_api_key",
        )

    if not endpoint.strip():
        return ValidationResult(
            is_valid=False,
            normalized_endpoint="",
            reason="missing_endpoint",
        )

    if not deployment.strip():
        return ValidationResult(
            is_valid=False,
            normalized_endpoint=normalize_openai_endpoint(endpoint, account_name),
            reason="missing_deployment",
        )

    normalized_endpoint = normalize_openai_endpoint(endpoint, account_name)
    parsed = urlparse(normalized_endpoint)
    host = parsed.netloc.lower()
    if not host.endswith(SUPPORTED_AZURE_OPENAI_HOST_SUFFIXES):
        return ValidationResult(
            is_valid=False,
            normalized_endpoint=normalized_endpoint,
            reason="invalid_endpoint",
        )

    return ValidationResult(
        is_valid=True,
        normalized_endpoint=normalized_endpoint,
        reason="ok",
    )
