# F1 OCR Event Persistence Research

Generated: 2026-02-20
Feature: `f1-ocr-event-persistence`

## Project Brief (Assumed from request + SPEC)

Goal:
- Implement F1 step-4 OCR event persistence for live lecture assistance.
- Add backend support for `POST /api/v4/lecture/visual/event` and save `visual_events` records.

In scope:
- visual event ingestion API (multipart)
- OCR result persistence (`visual_events`)
- quality handling (`good|warn|bad`)
- ownership and active-session checks
- test coverage for schema/service/API paths

Out of scope:
- 30-second summarization (`/lecture/summary/latest`)
- finalize workflow (`/lecture/session/finalize`)
- lecture index/search pipeline expansion
- frontend camera/OCR capture implementation

## Evidence from Current SPEC

From `docs/SPEC.md`:
- F1 requires OCR for slide/board regions and event persistence.
- API contract includes `POST /api/v4/lecture/visual/event` (multipart).
- Persisted entity `visual_events` fields include:
  - `session_id`, `timestamp_ms`, `source`, `ocr_text`, `ocr_confidence`, `quality`, `change_score`, `blob_path`, `created_at`
- Fallback policy: OCR failure should not crash the flow; record degraded quality and continue.

## Environment / Tooling Findings

- Gemini CLI command failed because `GEMINI_API_KEY` is missing.
- Therefore, research is consolidated from:
  - local codebase analysis
  - existing design documents
  - `docs/SPEC.md` constraints

## Practical Design Constraints

1. Existing lecture path is ownership-aware and should remain so
- keep `session_id + user_id` check before persistence
- reject unknown session with `404`
- reject non-active session with `409`

2. Multipart API shape should match SPEC without overloading route logic
- route parses form/file inputs
- service owns policy checks and persistence

3. OCR call should be behind an adapter boundary
- allows deterministic tests
- avoids hard-coupling route/service to Azure SDK details

4. Failure handling must be persistence-first
- OCR failure or low-confidence response should still create a `visual_event`
- quality set to `bad`/`warn` rather than raising unhandled exception

5. Privacy defaults should be conservative
- do not persist raw image bytes in DB
- `blob_path` nullable and optional for now

## Recommended API Contract (MVP)

Request (`multipart/form-data`):
- `session_id: str`
- `timestamp_ms: int`
- `source: slide|board`
- `change_score: float`
- `image: UploadFile` (jpeg)

Response (`200`):
- `event_id: str`
- `ocr_text: str`
- `ocr_confidence: float`
- `quality: good|warn|bad`

Validation:
- `timestamp_ms >= 0`
- `0.0 <= change_score <= 1.0`
- content type constrained to JPEG for MVP

## Quality Policy (Suggested)

Example threshold policy (configurable later):
- `good`: `ocr_confidence >= 0.80`
- `warn`: `0.50 <= ocr_confidence < 0.80`
- `bad`: `ocr_confidence < 0.50` or OCR processing failed

On OCR failure:
- persist record with
  - `ocr_text = ""`
  - `ocr_confidence = 0.0`
  - `quality = "bad"`
- return `200` to support audio-first fallback behavior in F1.

## Risks and Mitigations

1. External OCR instability
- Mitigation: adapter protocol + graceful fallback persistence

2. Multipart testing complexity
- Mitigation: add focused API tests with in-memory JPEG bytes

3. Contract drift from SPEC
- Mitigation: freeze schema/field names exactly as SPEC names

4. Future Azure integration churn
- Mitigation: keep OCR adapter implementation swappable via DI

## Open Questions for Approval

1. Should OCR provider integration be included now, or start with a deterministic fake OCR implementation plus adapter?
2. Should `blob_path` remain `null` in this feature, or should image upload to storage be included now?
3. Confirm desired HTTP behavior on OCR provider failure: `200` with `quality=bad` (recommended) vs non-2xx.
4. Confirm acceptable upload content types for MVP: JPEG-only vs JPEG+PNG.

## Success Criteria

- New `visual_events` records persist correctly for active, owned sessions.
- Endpoint returns OCR metadata (`event_id`, `ocr_text`, `ocr_confidence`, `quality`).
- Unknown/inactive/other-user sessions are blocked consistently.
- OCR failure path records `quality=bad` without breaking lecture flow.
- Tests pass for schema, service, and API layers.
