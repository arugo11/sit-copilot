"""Authentication dependencies for API routes."""

from hmac import compare_digest
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from app.core.config import settings

PROCEDURE_TOKEN_HEADER = "X-Procedure-Token"
_procedure_token_header = APIKeyHeader(name=PROCEDURE_TOKEN_HEADER, auto_error=False)
LECTURE_TOKEN_HEADER = "X-Lecture-Token"
USER_ID_HEADER = "X-User-Id"
_lecture_token_header = APIKeyHeader(name=LECTURE_TOKEN_HEADER, auto_error=False)
_user_id_header = APIKeyHeader(name=USER_ID_HEADER, auto_error=False)


async def require_procedure_token(
    token: Annotated[str | None, Depends(_procedure_token_header)],
) -> None:
    """Validate procedure API token from header."""
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized.",
        )

    if not compare_digest(token, settings.procedure_api_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized.",
        )


async def require_lecture_token(
    token: Annotated[str | None, Depends(_lecture_token_header)],
) -> None:
    """Validate lecture API token from header."""
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized.",
        )

    if not compare_digest(token, settings.lecture_api_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized.",
        )


async def require_user_id(
    user_id: Annotated[str | None, Depends(_user_id_header)],
) -> str:
    """Resolve current user ID from request header."""
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized.",
        )

    normalized_user_id = user_id.strip()
    if not normalized_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized.",
        )

    return normalized_user_id
