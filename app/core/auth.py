"""Authentication dependencies for API routes."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Final

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

PROCEDURE_TOKEN_HEADER = "X-Procedure-Token"
LECTURE_TOKEN_HEADER = "X-Lecture-Token"
USER_ID_HEADER = "X-User-Id"
DEMO_SESSION_KIND: Final[str] = "demo-session-v1"
DEMO_SCOPE_LECTURE: Final[str] = "lecture"
DEMO_SCOPE_PROCEDURE: Final[str] = "procedure"
_procedure_token_header = APIKeyHeader(name=PROCEDURE_TOKEN_HEADER, auto_error=False)
_lecture_token_header = APIKeyHeader(name=LECTURE_TOKEN_HEADER, auto_error=False)
_user_id_header = APIKeyHeader(name=USER_ID_HEADER, auto_error=False)
_authorization_header = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class DemoSessionClaims:
    """Parsed and verified demo session claims."""

    user_id: str
    scopes: tuple[str, ...]
    issued_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class AuthContext:
    """Request auth context resolved from legacy or demo credentials."""

    lecture_allowed: bool
    procedure_allowed: bool
    user_id: str | None
    demo_session: DemoSessionClaims | None


def _encode_base64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode_base64url(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _demo_session_signature(payload_segment: str) -> str:
    digest = hmac.new(
        settings.demo_session_secret.encode("utf-8"),
        payload_segment.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _encode_base64url(digest)


def build_demo_session_token(
    *,
    user_id: str,
    scopes: tuple[str, ...] = (DEMO_SCOPE_LECTURE, DEMO_SCOPE_PROCEDURE),
    now: datetime | None = None,
) -> tuple[str, datetime]:
    """Return signed token and expiry for public demo access."""
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(seconds=settings.demo_session_ttl_seconds)
    payload = {
        "kind": DEMO_SESSION_KIND,
        "user_id": user_id,
        "scopes": list(scopes),
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": uuid.uuid4().hex,
    }
    payload_segment = _encode_base64url(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = _demo_session_signature(payload_segment)
    return f"{payload_segment}.{signature}", expires_at


def _parse_demo_session_token(token: str) -> DemoSessionClaims | None:
    if "." not in token:
        return None

    payload_segment, signature = token.split(".", 1)
    expected_signature = _demo_session_signature(payload_segment)
    if not hmac.compare_digest(signature, expected_signature):
        return None

    try:
        payload = json.loads(_decode_base64url(payload_segment).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None

    if payload.get("kind") != DEMO_SESSION_KIND:
        return None

    user_id = str(payload.get("user_id", "")).strip()
    if not user_id:
        return None

    raw_scopes = payload.get("scopes", [])
    if not isinstance(raw_scopes, list):
        return None
    scopes = tuple(
        scope
        for scope in raw_scopes
        if isinstance(scope, str)
        and scope in {DEMO_SCOPE_LECTURE, DEMO_SCOPE_PROCEDURE}
    )
    if not scopes:
        return None

    try:
        issued_at = datetime.fromtimestamp(int(payload["iat"]), tz=UTC)
        expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=UTC)
    except (KeyError, TypeError, ValueError, OSError):
        return None

    if expires_at <= datetime.now(UTC):
        return None

    return DemoSessionClaims(
        user_id=user_id,
        scopes=scopes,
        issued_at=issued_at,
        expires_at=expires_at,
    )


def build_public_demo_user_id() -> str:
    """Return a stable random user identifier for one demo bootstrap."""
    return f"demo_{uuid.uuid4().hex[:12]}"


async def resolve_auth_context(
    lecture_token: Annotated[str | None, Depends(_lecture_token_header)],
    procedure_token: Annotated[str | None, Depends(_procedure_token_header)],
    user_id_header: Annotated[str | None, Depends(_user_id_header)],
    authorization: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_authorization_header)
    ],
) -> AuthContext:
    """Resolve current auth context from demo token or legacy headers."""
    candidate_tokens = [
        token
        for token in (
            lecture_token,
            procedure_token,
            authorization.credentials if authorization else None,
        )
        if token
    ]

    for token in candidate_tokens:
        claims = _parse_demo_session_token(token)
        if claims is None:
            continue
        return AuthContext(
            lecture_allowed=DEMO_SCOPE_LECTURE in claims.scopes,
            procedure_allowed=DEMO_SCOPE_PROCEDURE in claims.scopes,
            user_id=claims.user_id,
            demo_session=claims,
        )

    normalized_user_id = (user_id_header or "").strip() or None
    return AuthContext(
        lecture_allowed=bool(lecture_token)
        and hmac.compare_digest(lecture_token or "", settings.lecture_api_token),
        procedure_allowed=bool(procedure_token)
        and hmac.compare_digest(procedure_token or "", settings.procedure_api_token),
        user_id=normalized_user_id,
        demo_session=None,
    )


async def require_procedure_token(
    auth: Annotated[AuthContext, Depends(resolve_auth_context)],
) -> None:
    """Validate procedure API access from legacy or demo token."""
    if auth.procedure_allowed:
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized.",
    )


async def require_lecture_token(
    auth: Annotated[AuthContext, Depends(resolve_auth_context)],
) -> None:
    """Validate lecture API access from legacy or demo token."""
    if auth.lecture_allowed:
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized.",
    )


async def require_user_id(
    auth: Annotated[AuthContext, Depends(resolve_auth_context)],
) -> str:
    """Resolve current user ID from request auth context."""
    if auth.user_id:
        return auth.user_id

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized.",
    )


async def require_public_demo_enabled() -> None:
    """Guard public demo bootstrap when explicitly disabled."""
    if settings.public_demo_enabled:
        return
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Public demo is unavailable.",
    )


def resolve_rate_limit_user_id(request: Request, auth: AuthContext | None = None) -> str | None:
    """Resolve user ID for rate limiting when available."""
    if auth and auth.user_id:
        return auth.user_id

    user_id = request.headers.get(USER_ID_HEADER, "").strip()
    if user_id:
        return user_id
    return None
