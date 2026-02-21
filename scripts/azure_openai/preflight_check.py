#!/usr/bin/env python3
"""Preflight check for Azure OpenAI endpoint/deployment settings."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

DEFAULT_API_VERSION = "2024-10-21"
DEFAULT_TIMEOUT_SECONDS = 20


@dataclass(frozen=True)
class ValidationResult:
    """Validation outcome for Azure OpenAI runtime settings."""

    is_valid: bool
    normalized_endpoint: str
    reason: str


def _normalize_openai_endpoint(endpoint: str, account_name: str = "") -> str:
    normalized_endpoint = endpoint.strip().rstrip("/")
    if not normalized_endpoint:
        return ""

    parsed = urlparse(normalized_endpoint)
    host = parsed.netloc.lower()
    if host.endswith(".openai.azure.com"):
        return normalized_endpoint
    if host.endswith(".api.cognitive.microsoft.com") and account_name.strip():
        return f"https://{account_name.strip()}.openai.azure.com"
    return normalized_endpoint


def _validate_openai_config(
    *,
    api_key: str,
    endpoint: str,
    deployment: str,
    account_name: str = "",
) -> ValidationResult:
    if not api_key.strip():
        return ValidationResult(False, "", "missing_api_key")
    if not endpoint.strip():
        return ValidationResult(False, "", "missing_endpoint")

    normalized_endpoint = _normalize_openai_endpoint(endpoint, account_name)
    if not deployment.strip():
        return ValidationResult(False, normalized_endpoint, "missing_deployment")

    parsed = urlparse(normalized_endpoint)
    host = parsed.netloc.lower()
    if not host.endswith(".openai.azure.com"):
        return ValidationResult(False, normalized_endpoint, "invalid_endpoint")

    return ValidationResult(True, normalized_endpoint, "ok")


def _require_env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _classify_http_error(status_code: int, body_text: str) -> str:
    lowered = body_text.lower()
    if status_code == 404 and "deploymentnotfound" in lowered:
        return "deployment_not_found"
    if status_code in {401, 403}:
        return "auth_failed"
    if status_code == 404:
        return "endpoint_not_found"
    if status_code == 429:
        return "rate_limited"
    if status_code >= 500:
        return "server_error"
    return "http_error"


def _build_chat_completion_url(
    *,
    endpoint: str,
    deployment: str,
    api_version: str,
) -> str:
    normalized_endpoint = endpoint.rstrip("/")
    deployment_path = quote(deployment, safe="")
    return (
        f"{normalized_endpoint}/openai/deployments/{deployment_path}/chat/completions"
        f"?api-version={api_version}"
    )


def main() -> int:
    api_key = _require_env("AZURE_OPENAI_API_KEY")
    endpoint = _require_env("AZURE_OPENAI_ENDPOINT")
    account_name = _require_env("AZURE_OPENAI_ACCOUNT_NAME")
    deployment = _require_env("AZURE_OPENAI_MODEL")
    api_version = _require_env("AZURE_OPENAI_API_VERSION") or DEFAULT_API_VERSION
    timeout_seconds = int(
        _require_env("AZURE_OPENAI_TIMEOUT_SECONDS") or DEFAULT_TIMEOUT_SECONDS
    )

    validation = _validate_openai_config(
        api_key=api_key,
        endpoint=endpoint,
        deployment=deployment,
        account_name=account_name,
    )

    print(f"config_valid={validation.is_valid}")
    print(f"normalized_endpoint={validation.normalized_endpoint or '(empty)'}")
    print(f"reason={validation.reason}")
    print(f"deployment={deployment or '(empty)'}")

    if not validation.is_valid:
        print("probe_result=skipped")
        return 2

    url = _build_chat_completion_url(
        endpoint=validation.normalized_endpoint,
        deployment=deployment,
        api_version=api_version,
    )
    payload = {
        "messages": [
            {"role": "system", "content": "Return compact JSON only."},
            {
                "role": "user",
                "content": (
                    '{"ok":true,"note":"preflight"} をそのまま JSON で返してください。'
                ),
            },
        ],
        "temperature": 0,
        "max_tokens": 32,
        "response_format": {"type": "json_object"},
    }
    request = Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "api-key": api_key,
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            _ = response.read()
        print("probe_result=pass")
        return 0
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        category = _classify_http_error(exc.code, body)
        print("probe_result=fail")
        print(f"probe_failure={category}")
        print(f"http_status={exc.code}")
        return 3
    except URLError as exc:
        print("probe_result=fail")
        print("probe_failure=network_error")
        print(f"network_reason={exc.reason}")
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
