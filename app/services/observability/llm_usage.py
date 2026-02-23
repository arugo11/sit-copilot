"""LLM usage extraction utility for Azure OpenAI responses."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

__all__ = [
    "LLMUsage",
    "extract_usage",
    "MODEL_COSTS",
]

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LLMUsage:
    """Token usage extracted from an Azure OpenAI response."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    @property
    def prompt_cost(self) -> float:
        """Compute prompt cost in USD using gpt-5-nano Global pricing."""
        return self.prompt_tokens * MODEL_COSTS["gpt-5-nano"]["prompt"]

    @property
    def completion_cost(self) -> float:
        """Compute completion cost in USD using gpt-5-nano Global pricing."""
        return self.completion_tokens * MODEL_COSTS["gpt-5-nano"]["completion"]

    @property
    def total_cost(self) -> float:
        """Compute total cost in USD."""
        return self.prompt_cost + self.completion_cost


# Per-token costs (USD) — Azure OpenAI Global Standard pricing
# Source: https://azure.microsoft.com/ja-jp/pricing/details/azure-openai/
MODEL_COSTS: dict[str, dict[str, float]] = {
    "gpt-5-nano": {
        "prompt": 0.05 / 1_000_000,        # $0.05 per 1M tokens
        "completion": 0.40 / 1_000_000,     # $0.40 per 1M tokens
    },
    "gpt-4.1-nano": {
        "prompt": 0.10 / 1_000_000,         # $0.10 per 1M tokens
        "completion": 0.40 / 1_000_000,     # $0.40 per 1M tokens
    },
    "gpt-4.1-mini": {
        "prompt": 0.40 / 1_000_000,         # $0.40 per 1M tokens
        "completion": 1.60 / 1_000_000,     # $1.60 per 1M tokens
    },
    "gpt-4.1": {
        "prompt": 2.00 / 1_000_000,         # $2.00 per 1M tokens
        "completion": 8.00 / 1_000_000,     # $8.00 per 1M tokens
    },
}


def extract_usage(response_json: dict[str, Any]) -> LLMUsage | None:
    """Extract token usage from an Azure OpenAI Chat Completions response.

    Azure OpenAI always returns a top-level ``usage`` object::

        {
          "usage": {
            "prompt_tokens": 123,
            "completion_tokens": 45,
            "total_tokens": 168
          },
          ...
        }

    Args:
        response_json: Parsed JSON response from Azure OpenAI.

    Returns:
        LLMUsage dataclass or None when the field is missing / malformed.
    """
    try:
        usage = response_json.get("usage")
        if not isinstance(usage, dict):
            return None

        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        total_tokens = usage.get("total_tokens")

        if not isinstance(prompt_tokens, int) or not isinstance(
            completion_tokens, int
        ):
            return None

        return LLMUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens if isinstance(total_tokens, int) else (prompt_tokens + completion_tokens),
        )
    except Exception:  # noqa: BLE001
        logger.debug("failed to extract usage from Azure OpenAI response")
        return None
