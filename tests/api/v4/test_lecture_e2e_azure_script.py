"""Azure-backed end-to-end lecture scenario from scripted transcript."""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.core.auth import LECTURE_TOKEN_HEADER, USER_ID_HEADER

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "lecture_scripts"
    / "e2e_fake_lecture_stat_ml_ja.json"
)


def _read_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _pick_matches(candidates: list[str], text: str) -> list[str]:
    normalized = text.lower()
    return [term for term in candidates if term.lower() in normalized]


@pytest.mark.azure_e2e
@pytest.mark.asyncio
async def test_scenario_azure_api_e2e_from_script() -> None:
    """Run full lecture API scenario against Azure runtime using scripted data."""
    api_base_url = _read_env("AZURE_E2E_API_BASE_URL", "PROD_API_BASE_URL")
    lecture_token = _read_env(
        "AZURE_E2E_LECTURE_TOKEN",
        "LECTURE_API_TOKEN",
        "VITE_LECTURE_API_TOKEN",
    )
    user_id = _read_env("AZURE_E2E_USER_ID", "DEMO_USER_ID") or "demo-user"

    if not api_base_url or not lecture_token:
        pytest.skip(
            "azure_e2e requires API base URL and lecture token "
            "(AZURE_E2E_* or PROD_API_BASE_URL + LECTURE_API_TOKEN)."
        )

    script = json.loads(SCRIPT_PATH.read_text(encoding="utf-8"))
    speech_chunks: list[dict[str, Any]] = script["speech_chunks"]
    expected: dict[str, Any] = script["expected"]

    headers = {
        LECTURE_TOKEN_HEADER: lecture_token,
        USER_ID_HEADER: user_id,
    }
    timeout = httpx.Timeout(40.0, connect=15.0)

    async with httpx.AsyncClient(base_url=api_base_url.rstrip("/"), timeout=timeout) as client:
        started_at_ms = int(time.time() * 1000)
        session_id = ""

        try:
            start_payload = {
                "course_name": f"{script['session']['course_name']} ({int(time.time())})",
                "lang_mode": script["session"].get("lang_mode", "ja"),
                "camera_enabled": False,
                "consent_acknowledged": True,
            }
            start_response = await client.post(
                "/api/v4/lecture/session/start",
                headers=headers,
                json=start_payload,
            )
            assert start_response.status_code == 200, start_response.text
            session_id = start_response.json()["session_id"]

            for chunk in speech_chunks:
                start_ms = started_at_ms + int(chunk["offset_ms"])
                end_ms = start_ms + int(chunk["duration_ms"])
                ingest_payload = {
                    "session_id": session_id,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "text": chunk["text"],
                    "confidence": float(chunk.get("confidence", 0.95)),
                    "is_final": True,
                    "speaker": chunk.get("speaker", "teacher"),
                }
                ingest_response = await client.post(
                    "/api/v4/lecture/speech/chunk",
                    headers=headers,
                    json=ingest_payload,
                )
                assert ingest_response.status_code == 200, ingest_response.text
                assert ingest_response.json().get("accepted") is True
                await asyncio.sleep(0.15)

            summary_payload: dict[str, Any] | None = None
            for _ in range(8):
                summary_response = await client.get(
                    "/api/v4/lecture/summary/latest",
                    headers=headers,
                    params={"session_id": session_id, "force_rebuild": "true"},
                )
                assert summary_response.status_code == 200, summary_response.text
                summary_payload = summary_response.json()
                if summary_payload.get("status") == "ok" and summary_payload.get("summary", "").strip():
                    break
                await asyncio.sleep(1.0)

            assert summary_payload is not None
            assert summary_payload["status"] == "ok", summary_payload
            summary_text = summary_payload.get("summary", "")
            summary_terms = [
                item.get("term", "")
                for item in summary_payload.get("key_terms", [])
                if isinstance(item, dict)
            ]
            summary_surface = f"{summary_text} {' '.join(summary_terms)}"
            summary_hits = _pick_matches(expected["summary_required_terms"], summary_surface)
            assert len(summary_hits) >= 2, {
                "required": expected["summary_required_terms"],
                "surface": summary_surface,
            }

            keyterms_payload: dict[str, Any] | None = None
            transcript_candidates = [
                " ".join(chunk["text"] for chunk in speech_chunks),
                *[chunk["text"] for chunk in speech_chunks],
            ]
            for transcript_text in transcript_candidates:
                keyterms_response = await client.post(
                    "/api/v4/lecture/transcript/analyze-keyterms",
                    headers=headers,
                    json={
                        "session_id": session_id,
                        "transcript_text": transcript_text,
                        "lang_mode": script["session"].get("lang_mode", "ja"),
                    },
                )
                assert keyterms_response.status_code == 200, keyterms_response.text
                keyterms_payload = keyterms_response.json()
                if keyterms_payload.get("status") == "ok":
                    break
                await asyncio.sleep(0.4)

            assert keyterms_payload is not None
            keyterm_surface = " ".join(
                [
                    *(term.get("term", "") for term in keyterms_payload.get("key_terms", [])),
                    *keyterms_payload.get("detected_terms", []),
                ]
            )
            keyterm_hits = _pick_matches(expected["keyterms_required"], keyterm_surface)
            if keyterms_payload.get("status") == "ok":
                assert keyterm_hits, {
                    "required": expected["keyterms_required"],
                    "surface": keyterm_surface,
                }
            else:
                summary_keyterm_hits = _pick_matches(
                    expected["keyterms_required"],
                    " ".join(summary_terms),
                )
                assert summary_keyterm_hits, {
                    "keyterms_payload": keyterms_payload,
                    "summary_terms": summary_terms,
                }

            index_response: httpx.Response | None = None
            index_payload: dict[str, Any] = {}
            for _ in range(4):
                index_response = await client.post(
                    "/api/v4/lecture/qa/index/build",
                    headers=headers,
                    json={"session_id": session_id, "rebuild": True},
                )
                if index_response.status_code == 200:
                    index_payload = index_response.json()
                    if (
                        index_payload.get("status") in {"success", "skipped"}
                        and int(index_payload.get("chunk_count", 0)) > 0
                    ):
                        break
                await asyncio.sleep(2.0)

            assert index_response is not None
            assert index_response.status_code == 200, index_response.text
            assert index_payload.get("status") in {"success", "skipped"}, index_payload
            assert int(index_payload.get("chunk_count", 0)) > 0, index_payload

            supported_cfg = expected["supported_qa"]
            supported_response = await client.post(
                "/api/v4/lecture/qa/ask",
                headers=headers,
                json={
                    "session_id": session_id,
                    "question": supported_cfg["question"],
                    "lang_mode": script["session"].get("lang_mode", "ja"),
                    "retrieval_mode": "source-only",
                    "top_k": 5,
                    "context_window": 1,
                },
            )
            assert supported_response.status_code == 200, supported_response.text
            supported_payload = supported_response.json()
            assert supported_payload["confidence"] in {"high", "medium", "low"}
            assert len(supported_payload.get("sources", [])) > 0

            answer_surface = " ".join(
                [
                    supported_payload.get("answer", ""),
                    supported_payload.get("verification_summary") or "",
                ]
            )
            answer_hits = _pick_matches(supported_cfg["required_answer_terms"], answer_surface)
            assert answer_hits, {
                "required": supported_cfg["required_answer_terms"],
                "answer": supported_payload,
            }

            source_surface = " ".join(
                source.get("text", "")
                for source in supported_payload.get("sources", [])
                if isinstance(source, dict)
            )
            source_hits = _pick_matches(supported_cfg["required_source_terms"], source_surface)
            assert source_hits, {
                "required": supported_cfg["required_source_terms"],
                "sources": supported_payload.get("sources", []),
            }

            unsupported_cfg = expected["unsupported_qa"]
            unsupported_response = await client.post(
                "/api/v4/lecture/qa/ask",
                headers=headers,
                json={
                    "session_id": session_id,
                    "question": unsupported_cfg["question"],
                    "lang_mode": script["session"].get("lang_mode", "ja"),
                    "retrieval_mode": "source-only",
                    "top_k": 5,
                    "context_window": 1,
                },
            )
            assert unsupported_response.status_code == 200, unsupported_response.text
            unsupported_payload = unsupported_response.json()

            unsupported_surface = " ".join(
                [
                    unsupported_payload.get("answer", ""),
                    unsupported_payload.get("verification_summary") or "",
                    unsupported_payload.get("fallback") or "",
                ]
            )
            fail_closed_hits = _pick_matches(
                unsupported_cfg["expected_fail_closed_terms"],
                unsupported_surface,
            )
            assert fail_closed_hits or unsupported_payload.get("confidence") == "low", {
                "expected_fail_closed_terms": unsupported_cfg["expected_fail_closed_terms"],
                "response": unsupported_payload,
            }
            blocked_hits = _pick_matches(
                unsupported_cfg["disallowed_answer_terms"],
                unsupported_payload.get("answer", ""),
            )
            assert not blocked_hits, {
                "disallowed": unsupported_cfg["disallowed_answer_terms"],
                "answer": unsupported_payload.get("answer", ""),
            }

        finally:
            if session_id:
                await client.post(
                    "/api/v4/lecture/session/finalize",
                    headers=headers,
                    json={"session_id": session_id, "build_qa_index": False},
                )
