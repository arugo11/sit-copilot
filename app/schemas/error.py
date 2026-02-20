"""Common API error response schemas."""

from typing import Any

from pydantic import BaseModel, ConfigDict


class ErrorDetail(BaseModel):
    """Error body for API responses."""

    model_config = ConfigDict(extra="allow")

    code: str
    message: str
    details: Any = None


class ErrorResponse(BaseModel):
    """Standardized top-level error response."""

    error: ErrorDetail
