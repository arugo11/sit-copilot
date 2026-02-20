"""Common API error handling."""

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.error import ErrorDetail, ErrorResponse


def _build_error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
) -> JSONResponse:
    serialized_details = jsonable_encoder(details)
    payload = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            details=serialized_details,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register common exception handlers."""

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _build_error_response(
            status_code=400,
            code="validation_error",
            message="Invalid request parameters.",
            details=exc.errors(),
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(_: Request, exc: HTTPException) -> JSONResponse:
        details = exc.detail
        message = details if isinstance(details, str) else "Request failed."
        return _build_error_response(
            status_code=exc.status_code,
            code="http_error",
            message=message,
            details=details,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(_: Request, exc: Exception) -> JSONResponse:
        return _build_error_response(
            status_code=500,
            code="internal_server_error",
            message="Internal server error.",
            details={"type": type(exc).__name__},
        )
