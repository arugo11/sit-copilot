"""Shared Azure OpenAI endpoint normalization and validation."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class ValidationResult:
    """Validation outcome for Azure OpenAI runtime settings."""

    is_valid: bool
    normalized_endpoint: str
    reason: str


def normalize_openai_endpoint(endpoint: str, account_name: str = "") -> str:
    """Normalize endpoint to Azure OpenAI host when possible."""
    normalized_endpoint = endpoint.strip().rstrip("/")
    if not normalized_endpoint:
        return ""

    parsed = urlparse(normalized_endpoint)
    host = parsed.netloc.lower()
    if not host:
        return normalized_endpoint

    if host.endswith(".openai.azure.com"):
        return normalized_endpoint

    if host.endswith(".api.cognitive.microsoft.com") and account_name.strip():
        normalized_account = account_name.strip()
        return f"https://{normalized_account}.openai.azure.com"

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
    if not host.endswith(".openai.azure.com"):
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
