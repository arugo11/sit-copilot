# Sprint3 F1 Speech Events + Subtitle Display Research

## Project Brief

- Feature: `sprint3-f1-speech-events-and-subtitles`
- Goal: Deliver SPEC step 3 (`F1, 音声イベント保存 + 字幕表示`) on current backend foundation.
- Source of intent:
  - User request: "Sprint3（F1 音声イベント保存 + 字幕表示）"
  - `docs/SPEC.md` sections 5.2, 10.5, 16

### In Scope (Sprint3)

- `POST /api/v4/lecture/session/start`
- `POST /api/v4/lecture/speech/chunk`
- Persistence for:
  - `lecture_sessions`
  - `speech_events`
- Validation rules required for safe ingestion (consent, ranges, active session checks).
- API contract sufficient for frontend subtitle rendering continuity.

### Out of Scope (Sprint3)

- OCR ingestion (`/lecture/visual/event`) and vision integration
- 30-second summary generation (`/lecture/summary/latest`)
- Finalize/index build flow (`/lecture/session/finalize`, `lecture_chunks`, search indexing)
- Real Azure Speech token issuance and SDK integration
- Frontend implementation (React app is not present in this repository)

## Contract Constraints from SPEC

From `docs/SPEC.md`:

- F1 audio pipeline:
  - Frontend recognizes speech with Azure Speech SDK.
  - Partial subtitles are displayed on frontend.
  - Backend receives final subtitle events.
- API:
  - `POST /api/v4/lecture/session/start`
  - `POST /api/v4/lecture/speech/chunk`
- Data:
  - `lecture_sessions` stores session metadata and consent state.
  - `speech_events` stores timing, text, confidence, and finality.
- Safety:
  - No raw audio persistence by default.
  - Session start requires consent acknowledgment.

## Minimal Domain Contract (Recommended for Sprint3)

### Session Start Request

- `course_name: str`
- `course_id: str | null`
- `lang_mode: Literal["ja", "easy-ja", "en"]`
- `camera_enabled: bool`
- `slide_roi: list[int] | null`
- `board_roi: list[int] | null`
- `consent_acknowledged: bool`

### Session Start Response

- `session_id: str`
- `status: Literal["active"]`

### Speech Chunk Request

- `session_id: str`
- `start_ms: int` (`>= 0`)
- `end_ms: int` (`>= start_ms`)
- `text: str` (non-empty)
- `confidence: float` (`0.0 <= confidence <= 1.0`)
- `is_final: bool`
- `speaker: Literal["teacher", "unknown"]`

### Speech Chunk Response (MVP Acknowledgement)

- `event_id: str`
- `session_id: str`
- `accepted: bool`

## Key Constraints and Decisions

1. Subtitle display responsibility remains on frontend.
   - Backend Sprint3 guarantees persistence + acknowledgement for final events.
2. Only final subtitle events should be persisted in Sprint3.
   - If `is_final` is false, reject request (`400`) to keep ingestion contract explicit.
3. Session validity is mandatory before speech ingestion.
   - Session must exist and be `active`; otherwise reject (`404` or `409`).
4. Keep storage privacy-safe.
   - Persist text/timing/confidence metadata only.
   - Do not store raw audio payloads.

## Unresolved Items to Confirm During Approval

- Whether `POST /lecture/speech/chunk` should return only acknowledgement or include echoed subtitle text for easier client reconciliation.
- Whether lecture endpoints need token auth in Sprint3 or can remain unauthenticated in local MVP mode.
- Whether session ID format must follow sample style (`lec_YYYYMMDD_###`) or UUID-based ID is acceptable.

## Risks and Mitigations

- Risk: Scope creep into OCR/summary/finalize.
  - Mitigation: enforce Sprint3 boundary to session start + speech chunk only.
- Risk: Ambiguous subtitle-display responsibility in backend-only repo.
  - Mitigation: explicitly define acknowledgement contract and test it.
- Risk: Invalid/flooded speech events.
  - Mitigation: strict schema validation and active-session gate.
