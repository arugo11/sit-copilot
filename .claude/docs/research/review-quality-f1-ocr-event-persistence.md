# Quality Review: f1-ocr-event-persistence

## Scope

- Diff-based discovery fallback used (`git diff --name-only` empty).
- Focused review on delivered feature files:
  - `app/api/v4/lecture.py`
  - `app/services/lecture_live_service.py`
  - `app/services/vision_ocr_service.py`
  - `app/schemas/lecture.py`
  - `app/models/visual_event.py`

## Findings

### [Medium] OCR adapter failures are silently swallowed with no observability

- Evidence:
  - `app/services/lecture_live_service.py:190-196` catches broad `Exception` and forces fallback result without logging.
- Impact:
  - Real OCR outages, SDK regressions, and coding errors are hidden as normal `quality=bad` events.
  - Operational diagnosis becomes difficult, and latent defects can persist unnoticed.
- Recommendation:
  - Catch expected provider exceptions explicitly and emit structured logs/metrics.
  - Keep fallback behavior, but record failure reason in telemetry.

### [Low] Runtime provider wiring is hardcoded to Noop implementation

- Evidence:
  - `app/api/v4/lecture.py:36-38` always returns `NoopVisionOCRService`.
- Impact:
  - Even in non-local environments, visual ingest returns empty OCR unless router code is changed.
  - Increases chance of configuration drift between environments.
- Recommendation:
  - Introduce settings-based provider factory in DI (Noop for local/test, real provider for configured env).

### [Low] Request schema mixes transport concerns with service command contract

- Evidence:
  - `app/schemas/lecture.py:122-135` includes multipart transport metadata (`image_content_type`, `image_size`) inside domain request model.
- Impact:
  - Tightens coupling between HTTP parsing and service layer contracts.
  - Can make non-HTTP callers and future refactors more awkward.
- Recommendation:
  - Split transport validation (API layer) from service command model (domain fields only), or use a dedicated mapper.

## Positive Notes

- Architecture stays aligned with existing vertical slice (`router -> service -> model`).
- Ownership/status validation is centralized and reused (`_get_active_session`).
- Type coverage and schema constraints are generally strong and consistent with existing code style.
