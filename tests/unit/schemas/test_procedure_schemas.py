"""Unit tests for procedure schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.procedure import (
    ProcedureAskRequest,
    ProcedureAskResponse,
    ProcedureSource,
)


def test_procedure_ask_request_accepts_valid_payload() -> None:
    """ProcedureAskRequest should accept valid payload."""
    payload = {
        "query": "在学証明書はどこで発行できますか。",
        "lang_mode": "ja",
    }

    request = ProcedureAskRequest.model_validate(payload)

    assert request.query == payload["query"]
    assert request.lang_mode == payload["lang_mode"]


def test_procedure_ask_request_rejects_extra_fields() -> None:
    """ProcedureAskRequest should reject unknown fields."""
    payload = {
        "query": "在学証明書はどこで発行できますか。",
        "lang_mode": "ja",
        "unexpected": "value",
    }

    with pytest.raises(ValidationError):
        ProcedureAskRequest.model_validate(payload)


def test_procedure_ask_request_rejects_invalid_lang_mode() -> None:
    """ProcedureAskRequest should reject unsupported lang_mode."""
    payload = {
        "query": "在学証明書はどこで発行できますか。",
        "lang_mode": "fr",
    }

    with pytest.raises(ValidationError):
        ProcedureAskRequest.model_validate(payload)


def test_procedure_ask_response_requires_action_next() -> None:
    """ProcedureAskResponse should require action_next field."""
    payload = {
        "answer": "証明書発行機で発行できます。",
        "confidence": "high",
        "sources": [],
        "fallback": "",
    }

    with pytest.raises(ValidationError):
        ProcedureAskResponse.model_validate(payload)


def test_procedure_source_serializes_required_fields() -> None:
    """ProcedureSource should keep required source fields."""
    source = ProcedureSource(
        title="証明書発行案内",
        section="申請方法",
        snippet="在学証明書は証明書自動発行機で発行できます。",
        source_id="doc_012_c03",
    )

    dumped = source.model_dump()

    assert dumped["title"] == "証明書発行案内"
    assert dumped["section"] == "申請方法"
    assert dumped["source_id"] == "doc_012_c03"
