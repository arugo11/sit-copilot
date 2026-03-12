# Project Design Document

> This document tracks design decisions made during conversations.
> Updated automatically by the `design-tracker` skill.

## Local Lecture Runtime Recovery (2026-03-13)

### Decision Summary

- Preserved reachable Azure OpenAI regional endpoints such as
  `https://japaneast.api.cognitive.microsoft.com/` instead of rewriting them to
  `*.openai.azure.com`.
- Added deterministic local fallbacks for lecture assist features when Azure runtime is rate-limited or partially incompatible:
  - heuristic key-term extraction from transcript text,
  - minimal ASR year-typo correction fallback,
  - safe subtitle-review apply fallback for obvious local corrections when judge fails,
  - capped QA `Retry-After` wait to avoid 30-second stalls per question.
- Hydrated live assist toggles from persisted user settings so localhost live UI reflects
  `assistSummaryEnabled` / `assistKeytermsEnabled` immediately.
- Restored SSE snapshot payload compatibility by emitting `originalLangText` when a speech chunk was corrected in-place.
- Test isolation now defaults `azure_search_enabled=False` unless a test explicitly opts into Azure Search.

### Rationale

- Student-local runtime can resolve and call the regional cognitive endpoint, while the rewritten `resource.openai.azure.com` host is not reachable in this environment.
- Poster-promised localhost features must keep working even under Azure OpenAI `429` or payload incompatibilities; fail-closed or deterministic local fallback is preferable to silently disabling features.
- The live page already persisted assist preferences, but without hydration the UI misleadingly showed summary/key-term support as OFF after reload.
- Existing tests should not depend on operator-local `.env.azure.generated` Azure Search settings.

### Compatibility Rules

- Do not normalize regional Azure OpenAI endpoints away from a host that is already reachable.
- Heuristic fallbacks must remain transcript-grounded and avoid inventing unseen terms or unsupported answers.
- Live SSE payloads may include both `sourceLangText` (current corrected text) and `originalLangText` (pre-correction text) when available.
- Tests that require Azure Search must enable it explicitly via monkeypatch or dependency override.

### Changelog

- 2026-03-13: Preserved regional Azure OpenAI endpoints for localhost/student runtime.
- 2026-03-13: Added deterministic key-term and subtitle-review fallbacks plus capped QA retry waits.
- 2026-03-13: Hydrated live assist toggles from user settings and restored corrected-transcript SSE compatibility.

## Production ASR PostgreSQL Timestamp Fix (2026-03-13)

### Decision Summary

- Kept lecture runtime timestamps in epoch milliseconds end-to-end.
- Promoted PostgreSQL-backed timestamp-ms columns from `INTEGER` to `BIGINT` for:
  - `speech_events.start_ms/end_ms`
  - `summary_windows.start_ms/end_ms`
  - `lecture_chunks.start_ms/end_ms`
  - `visual_events.timestamp_ms`
- Added startup self-healing migration for PostgreSQL runtimes to coerce legacy `int4` columns to `int8`.
- Expanded production deploy smoke to verify lecture auth, session start, speech ingest with epoch ms, and finalize.

### Rationale

- Frontend live ingestion already emits `Date.now()`-scale epoch milliseconds.
- SQLite tolerates these values, but PostgreSQL `INTEGER` does not, causing production ASR ingest failure after auth succeeds.
- The observed browser-side CORS message was a secondary symptom; the root cause was a DB write-path failure in Container Apps logs.

### Compatibility Rules

- Do not shrink lecture timestamps to relative offsets just to satisfy legacy DB schemas.
- Any PostgreSQL runtime used for lecture live ingestion must keep timestamp-ms columns as `BIGINT`.
- Production smoke must verify at least one authenticated `speech/chunk` write with epoch ms.

### Changelog

- 2026-03-13: Added PostgreSQL `BIGINT` self-healing for lecture timestamp columns and production speech-ingest smoke coverage.

## Student Demo Runtime Hardening (2026-03-12)

### Decision Summary

- Standardized public student demo auth on build-time injected frontend headers:
  - `VITE_LECTURE_API_TOKEN`
  - `VITE_DEMO_USER_ID=demo-user`
- Rotated `sit-copilot-api` runtime `LECTURE_API_TOKEN` secret and redeployed frontend/backend together to avoid public `401 Unauthorized` drift.
- Added Azure Search legacy schema compatibility:
  - detect whether `keywords` field is `Collection(String)` or scalar,
  - normalize uploaded documents to scalar string when the existing index keeps legacy scalar schema.
- Added lecture QA fail-closed heuristics for answerer failures:
  - grounded deterministic answers for `year`, `attention`, `RNN/CNN`, `BERT/GPT` questions,
  - explicit `no_source` fallback for unsupported questions such as successor/exam claims.
- Kept summary recovery compatible with PostgreSQL by using dialect-specific upsert instead of SQLite-only insert helpers.

### Rationale

- Public frontend auth values are compiled into the bundle, so backend secret rotation without frontend rebuild causes immediate auth mismatch.
- Student Azure Search index already existed with a legacy `keywords` field shape; schema migration in-place was not allowed, so upload-time compatibility was safer than destructive index recreation.
- Azure OpenAI answer generation can fail transiently in student runtime. Deterministic grounded fallback is required to keep demo QA usable and to avoid hallucinated unsupported answers.
- Production student runtime uses PostgreSQL, so SQLite-specific summary persistence logic was not portable.

### Compatibility Rules

- Token rotation for public student demo must remain:
  1. update Container Apps secret,
  2. rebuild frontend with the same token/user id,
  3. redeploy both before validation.
- `demo-user` is the canonical public demo user id. `demo_user` should not be reintroduced in frontend defaults.
- Do not recreate the Azure Search index only to change `keywords` type in student environments unless a migration window is explicitly planned.
- When answerer fails, unsupported questions must prefer `no_source` over loosely related grounded snippets.

### Changelog

- 2026-03-12: Synchronized student demo token via build-time frontend injection and Container Apps secret rotation.
- 2026-03-12: Added Azure Search legacy `keywords` upload compatibility and QA fail-closed heuristics.

## Overview

Claude Code Orchestra is a multi-agent collaboration framework. Claude Code (200K context) is the orchestrator, with Codex CLI for planning/design/complex code, Gemini CLI (1M context) for codebase analysis, research, and multimodal reading, and subagents (Opus) for code implementation and Codex delegation.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Claude Code Lead (Opus 4.6 — 200K context)                      │
│  Role: Orchestration, user interaction, task management           │
│                                                                   │
│  ┌──────────────────────┐  ┌──────────────────────┐             │
│  │ Agent Teams (Opus)    │  │ Subagents (Opus)      │             │
│  │ (parallel + comms)    │  │ (isolated + results)  │             │
│  │                       │  │                       │             │
│  │ Researcher ←→ Archit. │  │ Code implementation   │             │
│  │ Implementer A/B/C     │  │ Codex consultation    │             │
│  │ Security/Quality Rev. │  │ Gemini consultation   │             │
│  └──────────────────────┘  └──────────────────────┘             │
│                                                                   │
│  External CLIs:                                                   │
│  ├── Codex CLI (gpt-5.3-codex) — planning, design, complex code  │
│  └── Gemini CLI (1M context) — codebase analysis, research,      │
│       multimodal reading                                          │
└─────────────────────────────────────────────────────────────────┘
```

## Billing Runaway Prevention and Leave-Stop Controls (2026-02-26)

### Decision Summary

- Fixed summary rebuild window baseline to start from the first event timestamp in the target session, not from epoch-aligned global windows.
- Added rebuild cap setting `LECTURE_SUMMARY_REBUILD_MAX_WINDOWS` (default: `1200`) and enforced capped latest-window rebuild when range is too large.
- Added no-data fast path in summary window build:
  - if both speech and visual events are empty for the window, skip LLM call and persist empty summary payload.
- Added operational repair script:
  - `scripts/repair_summary_windows.py`
  - default mode `local` (no Azure LLM), optional `azure` mode with resilient fallback.
- Updated lecture live page behavior to stop generation-related activity when user leaves active tab context:
  - on `visibilitychange=hidden` or `pagehide`: stop recording + disconnect SSE,
  - on `visibilitychange=visible`: reconnect SSE and resume recording only if recording was active before hide.
- Removed `autoTitleSessionId` route-state handoff from Live -> Lectures navigation to prevent automatic QA/title generation after leaving live session page.
- Hardened stream reconnection policy:
  - do not auto-reconnect on non-recoverable SSE connect errors (`401`, `404`).

### Rationale

- Azure billing spike root cause was unbounded session-window reconstruction from epoch baseline.
- Even after user navigation, background generation triggers (auto-title/stream reconnect loops) can continue unintended calls unless explicitly stopped.
- Local-first repair avoids additional cost while cleaning already-corrupted summary window data.

### Compatibility Rules

- No public lecture API schema changes.
- Existing session lifecycle semantics remain:
  - no auto-finalize on tab hide,
  - same session can resume after visibility recovery.
- Auto-title remains available via explicit/manual actions; only leave-triggered auto invocation is removed.

## Lecture QA Failure Handling and Runtime Simplification (2026-02-24)

### Decision Summary

- Disabled lecture question-classifier routing in runtime QA flow.
- Restored grounded local fallback on `answerer` failure when valid source text exists.
- Updated explicit failure messaging to include raw internal reason:
  - Japanese: `回答文生成に失敗しました。（理由: {raw_reason}）`
  - English: `Failed to generate answer. (Reason: {raw_reason})`
- Added process-shared `AzureOpenAILectureAnswererService` in API DI.
  - Recreate only when answerer-related settings key changes.
  - Keep Weave wrapper request-scoped (`ObservedLectureAnswererService`) around shared inner instance.
- Persist `qa_turns.outcome_reason` for lecture QA across all major branches:
  - `no_source`
  - `answerer_error_grounded`
  - `answerer_error_failure`
  - `verified`
  - `repaired_verified`
  - `verification_failed`

### Rationale

- Classification introduced an avoidable control-path fork and made recovery behavior inconsistent.
- Answer generation failures should degrade to evidence-first local snippets whenever possible, instead of generic failure text.
- Operators and users need failure transparency; exposing the raw reason improves diagnosability.
- Reusing answerer instances keeps retry and request-interval state stable across requests and reduces churn.
- Explicit `outcome_reason` persistence removes ambiguity (`unspecified`) and supports postmortem/analytics.

### Compatibility Rules

- External response schemas remain unchanged (`LectureAskResponse`, `LectureFollowupResponse`).
- Classifier settings remain in config for backward compatibility but are not used by lecture QA runtime path.
- Failure reason text is normalized and truncated defensively before rendering.

## Live Assist Summary Update Trigger Alignment (2026-02-24)

### Decision Summary

- Removed interval-based summary polling from `AssistPanel` (`30s` timer).
- Removed 3-chunk summary polling trigger from `LectureLivePage`.
- Automatic summary refresh is now triggered only when a new finalized subtitle line is observed.
- Stopped applying SSE `assist.summary` events directly in `LectureLivePage`; summary panel state is driven by subtitle-triggered `summary/latest` fetch.
- Added summary point deduplication in `liveSessionStore.setAssistSummary` to suppress no-op UI re-renders.

### Rationale

- Frequent automatic summary rewrites made active reading difficult.
- Subtitle-driven refresh keeps update timing aligned with visible transcript progression.
- Deduplicating unchanged summary points avoids flicker and unnecessary redraws.

### Compatibility Rules

- Manual `Refresh` action in summary panel remains available.
- Summary toggle and language switch no longer force immediate summary refresh; next finalized subtitle update will refresh automatically.

## Poster Screenshot Aspect-Ratio Adaptive UI Refresh (2026-02-24)

### Decision Summary

- Updated web-poster screenshot zone to an asymmetric two-panel layout:
  - Live panel width ratio: `1.65`
  - QA panel width ratio: `1.0`
- Bound frame aspect ratios to actual delivered assets:
  - `live-screen.png`: `1771 x 845` (wide)
  - `qa-screen.png`: `432 x 448` (near-square)
- Replaced inline screenshot styles with reusable CSS classes (`slot-header`, `slot-tag`, `screen-frame`, `qa-points`) to keep poster UI consistent and maintainable.
- Added concise QA-side guidance text so evaluators can quickly identify evidence-related UI elements.

### Rationale

- Prior equal-width `16:9` frames introduced excessive empty margins for the near-square QA capture and reduced legibility.
- Mixed-aspect framing keeps both images larger without wasting A0 area.
- Reusable class-based styling reduces future tweak cost and avoids repeated inline-style drift.

### Compatibility Rules

- Keep image asset paths unchanged:
  - `poster-gen/assets/images/live-screen.png`
  - `poster-gen/assets/images/qa-screen.png`
- Preserve `object-fit: contain` for screenshot rendering to avoid cropping source/evidence labels.
- For future image replacement, update frame aspect-ratio values first; avoid reintroducing fixed `16:9` containers.

## Poster QR Embedding Finalization (2026-02-24)

### Decision Summary

- Finalized poster QR assets under:
  - `poster-gen/assets/images/qr-demo-video.png`
  - `poster-gen/assets/images/qr-app-url.png`
  - `poster-gen/assets/images/qr-github.png`
- Generated app/GitHub QR codes with existing `poster-gen` utility:
  - app URL: `https://proud-sand-00bb37700.1.azurestaticapps.net/`
  - repository URL: `https://github.com/arugo11/sit-copilot`
- Updated QR UI in web poster to production-ready embedding:
  - removed "待ち" placeholder wording,
  - added explicit missing-asset fallback text with file path,
  - made app and GitHub QR cards clickable (`target="_blank"`, `rel="noopener noreferrer"`),
  - added short URL captions for scan/verification support.

### Rationale

- Placeholder-only rendering obscures whether QR assets are correctly embedded.
- Clickable web-preview cards improve evaluator flow while preserving print usability.
- Showing source URLs below QR improves trust and reduces scan ambiguity.

### Compatibility Rules

- Maintain square QR rendering (`1:1`) with `object-fit: contain`.
- Keep QR image paths stable; future replacements should overwrite the same file names.
- Keep app/repository links synchronized with QR generation targets when URLs change.

## Poster A0 Fit Convergence Loop (2026-02-25)

### Decision Summary

- Ran iterative `create -> evaluate -> adjust` cycles on `poster-gen/poster-preview.html` until web-poster output converged to A0 aspect.
- Convergence target:
  - Width: `3400 px`
  - Height: `4804 px` (A0 ratio `841:1189`)
- Final exported image:
  - `poster-gen/poster-preview-output.png` (`3400 x 4804`)
- Main adjustments applied during loops:
  - Removed zoom-control dependency for evaluation and moved to static poster rendering on screen.
  - Compressed typography and spacing across header/content/section blocks.
  - Reduced high-height content blocks in Row 3 (results/future-plans) while preserving core narrative.
  - Kept screenshot and QR image paths stable; only layout/typography were tuned.

### Rationale

- Initial poster exceeded A0 height significantly (`~3400 x 8870`) and could not be exported as a single-page A0-equivalent image.
- The dominant height contributor was dense Row 3 content and large baseline type/spacing values.
- Iterative measurement-based compression achieved target ratio without requesting new source images.

### Compatibility Rules

- Preserve A0 export ratio for image outputs:
  - `output_height = output_width * 1189 / 841`
- If future content additions push height over target again, apply this order:
  1. reduce verbose text blocks/tables,
  2. tighten spacing/typography,
  3. then review image proportions if still unresolved.
- Avoid non-uniform scaling (`scaleY`-only) for final poster exports.

## Poster Header Identity Emphasis Tuning (2026-02-25)

### Decision Summary

- Increased top-right identity text sizes to improve visibility at distance:
  - author name: `18pt -> 22pt`
  - affiliation: `14pt -> 17pt`
  - event badge: `10.5pt -> 13pt`
- Compensated with tighter vertical spacing (`margin-bottom` reductions) so overall A0 fit remains unchanged.

### Rationale

- The right-side identity block appeared visually underweighted relative to the main title.
- Competition/exhibit context requires faster identification of author/affiliation/event from 1-2m viewing distance.

### Compatibility Rules

- Keep final poster export size at A0 ratio (`3400 x 4804`) after any future header typography changes.
- If identity text is increased further, prefer reducing spacing before shrinking other core content.

## Poster Rubric-Driven Evidence Upgrade (2026-02-25)

### Decision Summary

- Reworked `poster-gen/poster-preview.html` to align with competition-required structure and scoring priorities.
- Added title-adjacent one-line outcome summary that explicitly states:
  - achieved: subtitle latency/quality
  - unmet: QA E2E latency (`9.18s` vs target `<5s`)
- Elevated central hero section from generic feature bullets to evidence-first AI usage representation:
  - kept system flow (`input -> caption -> summary -> source-only QA -> output`)
  - introduced process matrix with columns for AI service, input/settings, output, human decision, verification, and fix actions.
- Explicitly separated development-support AI usage from product-runtime AI usage to avoid evaluation ambiguity.
- Replaced metric cards with rubric-friendly evaluation table:
  - metric / measured / target / judgement / comment
  - includes `ASR correction latency 6.41s` and adoption constraint (`0/5`).
- Added reproducibility memo block listing:
  - measurement date/conditions
  - API-level measurement points
  - runtime AI stack and model notes (`gpt-5-nano`, record of `gpt-4.1-nano` operation for subtitle transform).
- Expanded analysis section with:
  - caption success factors
  - QA bottleneck hypotheses
  - constraints and interpretation
  - prioritized next actions (max 3).
- Added explicit safety mini-box:
  - source-only intent
  - fail-closed behavior for no-source cases
  - consent-first handling note.
- Synced `poster-gen/posters/sit-copilot.json` with factual metrics and constraints so data-driven regeneration remains coherent.

### Rationale

- The competition emphasizes practical AI orchestration and verification over model novelty.
- Previous layout showed features but under-expressed human validation loops and reproducibility.
- Rubric-weighted restructuring improves score potential in:
  - prompt/AI utilization (②),
  - model performance evidence (①),
  - analysis depth (④),
  while preserving A0 fit.

### Compatibility Rules

- Keep factual metrics unchanged unless backed by new measurement artifacts:
  - `0.76s`, `0.99s`, `5/5`, `9.18s`, `6.41s`.
- Preserve explicit disclosure of QA latency unmet status; do not hide unmet target.
- Keep `source-only` terminology consistent across flow/table/analysis/safety copy.
- Maintain A0 export ratio and current screenshot/QR asset paths.
- If demo video URL is still pending, retain "準備中/最終確認中" labeling and update only the URL/QR target when finalized.

### Changelog

- 2026-02-25: Rebuilt poster content into rubric-driven evidence structure and synchronized poster JSON facts with runtime metrics.

## Poster A0 Print Readability Hardening (2026-02-25)

### Decision Summary

- Rebuilt web poster layout in `poster-gen/poster-preview.html` for long-distance A0 readability and rubric-first scanning.
- Enforced large typography policy in print layout:
  - body copy at high-visibility scale,
  - tables enlarged and simplified,
  - caption-size floor retained for annotation text.
- Replaced dense/low-legibility structures:
  - competitor comparison table -> 3x4 check grid (3 tools max),
  - AI dense matrix -> compact `AI利用の要点` block + appendix-to-GitHub callout.
- Added immediate top-level evidence framing:
  - one-line core claim under title,
  - achieved/unmet pill row with explicit QA unmet disclosure.
- Rationalized section order to sequential numbering (`1..6`) and isolated demo links at bottom.
- Reduced screenshot area to one lecture screenshot with objective-mapped callouts.

### Rationale

- Prior version required close-range reading due high information density and small text in critical evidence areas.
- Competition judging requires instant claim recognition plus traceable evidence in 3-minute explanation windows.
- Shrinking text further was explicitly avoided; content volume was reduced instead.

### Compatibility Rules

- Preserve factual metrics and unmet-status disclosure as-is.
- Keep A0 output ratio (`3400 x 4804`) for preview exports.
- Keep demo video label honest (`準備中`) until URL is finalized.
- If additional details are needed, route to GitHub/docs callouts instead of re-densifying on-poster tables.

### Changelog

- 2026-02-25: Applied A0 readability-first poster restructure with top-level performance pills, simplified AI usage presentation, and sequential sectioning.

## Poster Evidence Label and Demo QR Simplification (2026-02-25)

### Decision Summary

- Removed printed URL strings from poster demo cards and kept QR-first access wording only.
  - app card: `QRでアクセス`
  - GitHub card: `QRで手順を見る`
- Filled unused left-side area in system overview with two high-readability blocks:
  - before/during/after mini timeline,
  - per-step AI usage mini table.
- Unified user-facing citation terminology to:
  - `source_id (S-001)` across constraints, prompt snippets, and screenshot callouts.
- Added explicit quality definition line for subtitle quality `5/5` using documented wording from performance evaluation.
- Added `✓` / `✕` symbols in KPI pills so status does not rely on color only.
- Localized demo heading from English to Japanese (`デモ`) for language consistency.

### Rationale

- URL text under QR cards reduced readability without adding practical value in print context.
- Section 3 had visible dead space that could be converted into rubric-relevant explanatory content.
- Mixed citation terms (`chunk_id` vs `S-001`) caused interpretation friction during judging.
- Color-independent status encoding improves accessibility and distance comprehension.

### Compatibility Rules

- Keep fact values unchanged (`0.76s`, `0.99s`, `5/5`, `9.18s`, `6.41s`).
- Keep demo video state explicit as pending (`準備中`) until URL finalization.
- Continue using `source_id (S-001)` as the poster-facing citation label.

### Changelog

- 2026-02-25: Removed printed URLs in demo area, unified citation label to `source_id`, and filled Section 3 whitespace with timeline/AI-step blocks.

## Poster Neutral KPI Framing and Language Cleanup (2026-02-25)

### Decision Summary

- Removed failure-emphasis wording from top KPI pill row and replaced third pill with positive capability statement:
  - `source-only QA` + citation display.
- Simplified Objective section bullets to role/scope statements and removed policy-like goal/unmet wording.
- Reworked Results table from `指標/実測/目標/判定` to `指標/実測/補足` to keep factual metrics while reducing judgment framing.
- Replaced overclaim phrasing for subtitle quality with documented definition:
  - quality `5/5` under LLM-as-a-Judge five-level scale, with doc reference.
- Renamed analysis section labels to neutral operational phrasing:
  - removed explicit `未達`/`目標` terms from headings.
- Updated demo-video card from pending-language to neutral active-language (`デモ動画`, `QRで視聴`) and removed staff-note text block.
- Replaced mixed English/Japanese constraint text in key prompt/constraint copy with plain Japanese while keeping factual semantics.

### Rationale

- Poster should keep evidence factual and concrete without sounding defensive or policy-driven.
- Judge readability improves when metrics are shown as measurements plus operational notes, not pass/fail labels.
- QR-first print layout does not need long URL strings or operational staff prose.

### Compatibility Rules

- Numeric metrics remain unchanged (`0.76s`, `0.99s`, `5/5`, `9.18s`, `6.41s`).
- No new numeric claims were introduced.
- Keep citation label consistent as `source_id (S-001)` across UI-facing poster text.

### Changelog

- 2026-02-25: Neutralized KPI/result wording, removed printed URL dependence, and aligned prompt/constraint phrasing with QR-first poster style.

## A0 Technical Poster Layout for SIT Copilot (2026-02-23)

### Decision Summary

- Target size: A0 portrait (`841 x 1189 mm`) for academic/technical showcase.
- Grid system: 12-column master grid with modular rows to balance dense technical content and readability at 1-2m viewing distance.
- Section structure fixed to:
  - Background
  - Objectives
  - AI Usage (real-time captioning, Q&A, OCR)
  - Results
  - Future Plans
- Architecture visuals should use one primary system diagram plus feature-specific mini-flows, with consistent icon and arrow semantics.
- Color direction prioritizes technical clarity over decorative style:
  - neutral light background
  - blue-cyan primary tones
  - limited warm accent for key metrics/callouts
- Typography is optimized for large-format scanning with explicit role-based size tiers (title, section, body, caption).

### Rationale

- Technical poster audiences scan quickly first, then deep-read selected blocks; strong top-down hierarchy and predictable section order reduce cognitive load.
- A single unified grid makes mixed content (text, charts, architecture diagrams, screenshots) easier to align and compare.
- High-contrast but restrained colors improve readability under conference venue lighting and long viewing sessions.

### Compatibility Rules

- Diagram labels must use the same terminology as product/API naming (`captioning`, `qa`, `ocr`) to avoid interpretation mismatch.
- Any screenshot or UI mock should align to grid columns; no floating unaligned visuals.
- Accent color usage must remain <=10% of poster area to preserve emphasis.

## PptxGenJS A0 Poster Generation Architecture (2026-02-23)

### Decision Summary

- Build a composition-first TypeScript module structure:
  - `poster/layout.ts`: A0 constants, mm/inch conversion, safe-area and grid calculation.
  - `poster/theme.ts`: color tokens, typography scale, and default shape/text styles.
  - `poster/schema.ts`: JSON schema and runtime validator for poster content.
  - `poster/components/*`: reusable render blocks (`header`, `section`, `text_block`, `figure`, `metric_card`, `footer`).
  - `poster/renderer/*`: thin PptxGenJS adapters (`addText`, `addShape`, `addImage`) with guardrails.
  - `poster/build.ts`: orchestration pipeline (`load -> validate -> layout -> render -> write`).
  - `poster/cli.ts`: CLI entry for config path and output path.
- Treat poster content as data (JSON), not imperative slide code, to keep presentation logic maintainable.
- Standardize reusable component contract:
  - `measure(block, ctx) -> Box`
  - `render(block, ctx) -> void`
  - optional `preflight(block, assets) -> ValidationResult`
- Manage configuration with layered merge order:
  - `defaults` -> `theme preset` -> `poster config` -> `CLI/env overrides`.
- Keep PptxGenJS usage constrained to infrastructure layer:
  - use `defineLayout` for A0 (`33.11 x 46.81 in`);
  - use `defineSlideMaster` for static branding/backplate;
  - write output via `writeFile()` in CLI and `write({ outputType: "nodebuffer" })` for tests.

### Rationale

- Data-driven rendering enables content-only updates without touching rendering code.
- Renderer isolation reduces API-change blast radius and improves testability.
- Measure/render split prevents overlap regressions on dense A0 layouts.
- Layered config supports multiple poster variants while preserving shared standards.

### Compatibility Rules

- Centralize all coordinate math in `layout.ts`; do not hardcode dimensions in components.
- Validate JSON schema before rendering and fail fast with human-readable errors.
- Avoid deprecated PptxGenJS API aliases; prefer current enum names and option keys.
- Images must preserve aspect ratio (`contain`/`crop`) and be checked for print-quality DPI.
- Keep master slide content static; place dynamic research content only through components.

## Frontend Demo Simplification & Streaming-Ready UI (2026-02-22)

### Decision Summary

- Removed login-first assumption in frontend flow and unified to demo-start CTA.
- Kept backend unchanged; frontend uses demo headers (`X-Lecture-Token`, `X-User-Id`) for API calls.
- Replaced lecture-list server dependency with session-start local persistence for demo stability.
- Introduced streaming abstraction with transport boundary:
  - `StreamClient` as UI-facing API
  - `MockStreamTransport` active implementation for current demo
  - `WebSocketTransport` and `SseTransport` scaffolds for future backend streaming
- Added Zustand stores for:
  - live session UI state
  - review QA streaming state
  - microphone input state
- Implemented microphone input hook (`getUserMedia` + `MediaRecorder`) and chunk handoff interface for future API wiring.
- Implemented block-based streaming UI:
  - Live transcript partial/final card progression
  - Review QA answer chunk-by-chunk append and done finalization
- Implemented backend SSE endpoint `GET /api/v4/lecture/events/stream` (header-auth protected, session-scoped).
- Implemented fetch-based `SseTransport` (header-capable) and connected it to `StreamClient` reconnect state machine.
- Added SSE failure fallback path: live page auto-switches to `MockStreamTransport` for demo continuity.

### Rationale

- Demo reliability improves by eliminating auth UI and non-existent list APIs.
- Streaming transport isolation minimizes migration cost when moving from mock to real WS/SSE.
- Block-based progressive rendering improves readability and supports accessibility announcements.

### Compatibility Rules

- UI layer must only depend on `StreamClient`, never transport-specific classes.
- Event boundaries `qa.answer.chunk` and `qa.answer.done` are contract-stable and must remain unchanged.
- In development, API base defaults to same-origin (`VITE_API_BASE_URL` unset) so Vite proxy can avoid CORS setup overhead.
- SSE client must use fetch-stream parsing (not `EventSource`) because auth requires custom headers.

### Review QA Real API Integration (2026-02-21)

#### Decision Summary

- Replaced review-page QA generation from `MockStreamTransport` to real API requests:
  - `POST /api/v4/lecture/qa/ask`
  - `POST /api/v4/lecture/qa/followup`
- Preserved existing block UI by converting each API response into one synthetic stream block pair:
  - one `qa.answer.chunk`
  - one `qa.answer.done`
- Added one-time async warmup call to `POST /api/v4/lecture/qa/index/build` with `rebuild=false`.
- Follow-up policy is deterministic:
  - first successful turn uses `ask`
  - subsequent turns use `followup` with `history_turns=3`.
- Citation mapping is fixed for this phase:
  - `speech -> audio`
  - `visual -> ocr`
  - citation ID format: `${answerId}::${chunk_id}::${index}`.

#### Compatibility Rules

- Review QA does not require server-side streaming in this phase.
- `followups` chips remain empty because current QA API response has no follow-up suggestion array.
- `404` on QA calls is treated as session mismatch and should navigate users back to lecture list.
- `fallback` responses are rendered as successful answers with low-confidence warning UI.

### Agent Roles

| Agent | Role | Responsibilities |
|-------|------|------------------|
| Claude Code（メイン） | 全体統括 | ユーザー対話、タスク管理、簡潔なコード編集 |
| general-purpose（Opus） | 実装・Codex委譲 | コード実装、Codex委譲、ファイル操作 |
| gemini-explore（Opus） | 大規模分析・調査 | コードベース理解、外部リサーチ、マルチモーダル読取 |
| Codex CLI | 計画・難実装 | アーキテクチャ設計、実装計画、複雑なコード、デバッグ |
| Gemini CLI（1M context） | 分析・調査・読取 | コードベース分析、外部リサーチ、マルチモーダル読取 |

---

## Sprint0 Backend Architecture (2026-02-21)

### Project: FastAPI Backend Foundation

**Goal**: Create FastAPI backend foundation with green pytest and /health endpoint returning 200.

### Directory Structure

```
sit-copilot/
├── app/                          # Main application module
│   ├── __init__.py
│   ├── main.py                   # FastAPI instance & root router
│   │
│   ├── api/                      # API routes (versioned)
│   │   ├── __init__.py
│   │   └── v4/                   # API v4
│   │       ├── __init__.py
│   │       └── health.py         # Health endpoint
│   │
│   ├── core/                     # Core infrastructure
│   │   ├── __init__.py
│   │   └── config.py             # Settings, environment variables
│   │
│   └── schemas/                  # Pydantic models
│       ├── __init__.py
│       └── health.py             # Health response schema
│
├── tests/                        # pytest tests
│   ├── __init__.py
│   ├── conftest.py               # Shared fixtures
│   ├── api/
│   │   ├── __init__.py
│   │   └── test_health.py        # Health endpoint tests
│   └── unit/
│       └── (future unit tests)
│
├── pyproject.toml                # Project config & dependencies
└── README.md
```

### Layered Architecture

```
┌─────────────────────────────────┐
│   API Layer (routes)            │  ← HTTP endpoints only
├─────────────────────────────────┤
│   Service Layer (business)      │  ← Business logic (future)
├─────────────────────────────────┤
│   Repository Layer (data)       │  ← CRUD operations (future)
├─────────────────────────────────┤
│   Model Layer (database)        │  ← ORM definitions (future)
└─────────────────────────────────┘
```

### Dependencies (pyproject.toml)

```toml
[project]
name = "sit-copilot"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.32",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.1",
    "pytest-mock>=3.12",
    "pytest-asyncio>=0.25.1",  # Critical: asyncio_mode = "auto" required
    "httpx>=0.26",             # For ASGITransport
    "ruff>=0.8",
    "ty>=0.11",
]

# Tool configurations
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"  # REQUIRED for FastAPI async tests
addopts = [
    "-v",
    "--cov=app",
    "--cov-report=term-missing",
]

[tool.ruff]
target-version = "py311"
line-length = 88

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "UP",     # pyupgrade
    "ASYNC",  # flake8-async (important for FastAPI)
]
ignore = ["E501"]  # formatter handles

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]  # Allow unused imports

[tool.ty]
strict = true
disallow_untyped_defs = true

[[tool.ty.overrides]]
module = "tests.*"
disallow_untyped_defs = false
```

### Pytest Fixture Architecture

**Modern 2025 approach**: Use `httpx.AsyncClient` with `ASGITransport`

```python
# tests/conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture(scope="session")
def event_loop():
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def async_client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac
```

### Health Endpoint Design

```python
# app/api/v4/health.py
from fastapi import APIRouter, status
from app.schemas.health import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])

@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=HealthResponse,
)
async def get_health() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="healthy")

# app/schemas/health.py
from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"
```

### Implementation Plan

| Step | Task | Dependencies |
|------|------|--------------|
| 1 | Initialize pyproject.toml with uv | None |
| 2 | Create directory structure | 1 |
| 3 | Create core/config.py (settings) | 2 |
| 4 | Create schemas/health.py | 2 |
| 5 | Create main.py (FastAPI app) | 2, 3 |
| 6 | Create api/v4/health.py (route) | 4, 5 |
| 7 | Write tests/conftest.py (fixtures) | 5 |
| 8 | Write tests/api/test_health.py | 6, 7 |
| 9 | Run pytest (TDD: should pass) | 8 |
| 10 | Verify /api/v4/health returns 200 | 9 |

### Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| pytest-asyncio compatibility | Medium | Use >=0.24 for Python 3.11, configure with `asyncio_mode = auto` |
| AsyncClient vs TestClient | Low | AsyncClient is 2025 best practice, use ASGITransport |
| ruff + ty compatibility | Low | Both from Astral, work well together |

---

## Sprint1 Settings API & SQLite Persistence (2026-02-20)

### Project: User Settings API with SQLite

**Goal**: Implement SQLite persistence and user settings API (GET/POST /api/v4/settings/me) as foundation for future features.

### Scope
- **Include**: SQLAlchemy setup, DB session management, users table, settings API, Pydantic schemas, common error responses
- **Exclude**: Azure connection, LLM, lecture functionality

### Success Criteria
- pytest passes
- GET/POST /api/v4/settings/me works
- Validation errors return 400
- Response JSON matches specification

### Directory Structure (Updated)

```
sit-copilot/
├── app/
│   ├── main.py                    # FastAPI app
│   ├── api/
│   │   └── v4/
│   │       ├── __init__.py
│   │       ├── health.py          # (existing)
│   │       └── settings.py        # NEW: Settings API endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py              # (existing, add database_url)
│   ├── db/
│   │   ├── __init__.py            # NEW: Database infrastructure
│   │   ├── base.py                # NEW: SQLAlchemy Base
│   │   └── session.py             # NEW: Async session dependency
│   ├── models/
│   │   ├── __init__.py            # NEW: ORM models
│   │   └── user_settings.py       # NEW: UserSettings model
│   ├── services/
│   │   ├── __init__.py            # NEW: Business logic layer
│   │   └── settings_service.py    # NEW: SettingsService
│   └── schemas/
│       ├── __init__.py
│       ├── health.py              # (existing)
│       └── settings.py            # NEW: Settings request/response schemas
│
├── tests/
│   ├── conftest.py                # (existing, add db fixture)
│   ├── api/
│   │   └── v4/
│   │       ├── __init__.py
│   │       ├── test_health.py     # (existing)
│   │       └── test_settings.py   # NEW: Settings API tests
│   └── unit/
│       ├── __init__.py
│       ├── schemas/
│       │   └── test_settings_schemas.py   # NEW: Schema validation tests
│       └── services/
│           └── test_settings_service.py   # NEW: Service layer tests
│
└── pyproject.toml                 # (add dependencies)
```

### Data Model

#### UserSettings Table

```python
# app/models/user_settings.py
from sqlalchemy import String, DateTime, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

class UserSettings(Base):
    __tablename__ = "user_settings"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_settings_user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

**Design Rationale**:
- One row per user (simpler queries, better performance)
- JSON column for flexible settings (theme, notifications, language, etc.)
- Unique constraint on user_id (prevents duplicates)
- Timestamps for auditing

**CRITICAL: JSON Mutation Tracking**
When mutating JSON fields, always call `flag_modified()` to ensure SQLAlchemy tracks changes:
```python
from sqlalchemy.orm.attributes import flag_modified

user_settings.settings = {"theme": "dark"}
flag_modified(user_settings, "settings")  # REQUIRED
```
Without `flag_modified()`, changes may not be persisted to the database.

### DB Session Management

```python
# app/db/session.py
from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

engine = create_async_engine(
    "sqlite+aiosqlite:///./sit_copilot.db",
    echo=False,
)

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # REQUIRED: Prevents lazy loading errors
)

async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency for database session with auto-commit."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()  # Auto-commit on success
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

**Key Configuration**:
- `expire_on_commit=False` prevents detached instance errors
- **Auto-commit on success** (simpler route handlers)
- Auto-rollback on exception
- Explicit session close in finally block

### Service Layer Architecture

```python
# app/services/settings_service.py
from typing import Protocol

class SettingsService(Protocol):
    """Interface for settings operations."""

    async def get_my_settings(self, user_id: str) -> SettingsResponse:
        """Get user settings. Returns empty dict if not found."""
        ...

    async def upsert_my_settings(
        self, user_id: str, request: SettingsUpsertRequest
    ) -> SettingsResponse:
        """Create or update user settings."""
        ...
```

**Design Pattern**:
- Protocol interface for testability
- Implementation separated from interface
- Business logic in service, not in routes

### API Contract

#### GET /api/v4/settings/me

**Response (200)**:
```json
{
    "user_id": "user123",
    "settings": {
        "theme": "dark",
        "notifications_enabled": true,
        "language": "ja"
    },
    "updated_at": "2026-02-20T12:00:00Z"
}
```

#### POST /api/v4/settings/me

**Request**:
```json
{
    "settings": {
        "theme": "light",
        "new_field": "value"
    }
}
```

**Response (200)**: Same as GET

**Validation Error (400)**:
```json
{
    "detail": [
        {
            "type": "dict_type",
            "loc": ["body", "settings"],
            "msg": "Input should be a valid dictionary",
        }
    ]
}
```

### Dependencies to Add

```toml
[project]
dependencies = [
    "fastapi>=0.110",
    "pydantic-settings>=2.13.1",
    "uvicorn[standard]>=0.32",
    "sqlalchemy[asyncio]>=2.0",  # NEW: Async support
    "aiosqlite>=0.21.0",         # NEW: SQLite async driver (Feb 2025)
]
```

### TDD Implementation Plan

| Step | Task | Dependencies | Test Type |
|------|------|--------------|-----------|
| 1 | Add dependencies (sqlalchemy, aiosqlite) | None | - |
| 2 | Create db/base.py, db/session.py | 1 | Unit |
| 3 | Create models/user_settings.py | 2 | Unit |
| 4 | Create schemas/settings.py | None | Unit (Pydantic) |
| 5 | Create test_settings_schemas.py (failing) | 4 | Unit |
| 6 | Implement schemas/settings.py | 5 | Unit |
| 7 | Create test_settings_service.py (failing) | 3, 6 | Unit |
| 8 | Implement services/settings_service.py | 7 | Unit |
| 9 | Create test_settings.py API tests (failing) | 8 | Integration |
| 10 | Implement api/v4/settings.py routes | 9 | Integration |
| 11 | Register router in main.py | 10 | Integration |
| 12 | Run pytest -v (all green) | 11 | E2E |
| 13 | Run ruff check . && ty check app/ | 12 | Quality |

### Common Error Response Schema

```python
# app/schemas/error.py (optional, for consistency)
from pydantic import BaseModel

class ErrorResponse(BaseModel):
    detail: list[dict[str, Any]] | str
```

FastAPI provides this automatically via Pydantic validation, but explicit schema enables documentation.

### Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| aiosqlite compatibility | Medium | Use >=0.20, verify with test suite first |
| JSON column limitations | Low | SQLite supports JSON operations; fallback to TEXT if needed |
| Async session leaks | High | Use dependency injection, context managers, pytest fixtures |
| Migration complexity | Medium | Use Alembic for production; simple CREATE TABLE for demo |
| Test database state | Medium | Use in-memory SQLite (`:memory:`) for tests |

### Testing Strategy

#### Unit Tests
- **Schema validation**: Pydantic model tests
- **Service layer**: Mock DB session, test business logic

#### Integration Tests
- **API endpoints**: Use AsyncClient with ASGITransport
- **Database operations**: Use in-memory SQLite fixture

```python
# tests/conftest.py (updated)
@pytest.fixture
async def db_session():
    """In-memory SQLite for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
```

### Detailed File Structure

```
app/
├── db/
│   ├── __init__.py
│   ├── base.py              # DeclarativeBase import
│   └── session.py           # engine, AsyncSessionFactory, get_db_session
├── models/
│   ├── __init__.py
│   └── user_settings.py     # UserSettings ORM model
├── services/
│   ├── __init__.py
│   └── settings_service.py  # SettingsService Protocol + implementation
├── schemas/
│   ├── __init__.py
│   ├── health.py            # (existing)
│   └── settings.py          # SettingsUpsertRequest, SettingsResponse
└── api/v4/
    ├── __init__.py
    ├── health.py            # (existing)
    └── settings.py          # GET/POST /settings/me routes
```

### Service Layer Implementation Details

```python
# app/services/settings_service.py (implementation example)
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from app.models.user_settings import UserSettings
from app.schemas.settings import SettingsUpsertRequest, SettingsResponse

class SqlAlchemySettingsService:
    """SQLAlchemy implementation of SettingsService."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_my_settings(self, user_id: str) -> SettingsResponse:
        result = await self._db.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        user_settings = result.scalar_one_or_none()
        if user_settings:
            return SettingsResponse(
                user_id=user_settings.user_id,
                settings=user_settings.settings,
                updated_at=user_settings.updated_at,
            )
        return SettingsResponse(user_id=user_id, settings={}, updated_at=None)

    async def upsert_my_settings(
        self, user_id: str, request: SettingsUpsertRequest
    ) -> SettingsResponse:
        result = await self._db.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        user_settings = result.scalar_one_or_none()

        if user_settings:
            # CRITICAL: Must use flag_modified() for JSON mutations
            user_settings.settings = request.settings
            flag_modified(user_settings, "settings")
        else:
            user_settings = UserSettings(user_id=user_id, settings=request.settings)
            self._db.add(user_settings)

        await self._db.commit()
        await self._db.refresh(user_settings)
        return SettingsResponse(
            user_id=user_settings.user_id,
            settings=user_settings.settings,
            updated_at=user_settings.updated_at,
        )
```

**IMPORTANT**: When mutating JSON fields, always call `flag_modified()` to ensure SQLAlchemy tracks the change. Without this, changes may not be persisted.

### API Routes Implementation

```python
# app/api/v4/settings.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.settings import SettingsUpsertRequest, SettingsResponse
from app.services.settings_service import SqlAlchemySettingsService

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("/me", status_code=status.HTTP_200_OK, response_model=SettingsResponse)
async def get_settings(
    db: AsyncSession = Depends(get_db),
) -> SettingsResponse:
    """Get current user's settings."""
    # TODO: Replace with actual user_id from auth
    user_id = "demo_user"
    service = SqlAlchemySettingsService(db)
    return await service.get_my_settings(user_id)

@router.post("/me", status_code=status.HTTP_200_OK, response_model=SettingsResponse)
async def update_settings(
    request: SettingsUpsertRequest,
    db: AsyncSession = Depends(get_db),
) -> SettingsResponse:
    """Update current user's settings."""
    # TODO: Replace with actual user_id from auth
    user_id = "demo_user"
    service = SqlAlchemySettingsService(db)
    return await service.upsert_my_settings(user_id, request)
```

### Test Cases to Cover

#### Schema Tests (`tests/unit/schemas/test_settings_schemas.py`)
- [x] SettingsUpsertRequest accepts valid dict
- [x] SettingsUpsertRequest rejects non-dict
- [x] SettingsUpsertRequest rejects extra fields (extra="forbid")
- [x] SettingsResponse serializes correctly

#### Service Tests (`tests/unit/services/test_settings_service.py`)
- [x] get_my_settings returns empty dict when user not found
- [x] get_my_settings returns existing settings
- [x] upsert_my_settings creates new user settings
- [x] upsert_my_settings updates existing settings
- [x] upsert_my_settings updates updated_at timestamp

#### API Tests (`tests/api/v4/test_settings.py`)
- [x] GET /api/v4/settings/me returns 200
- [x] GET /api/v4/settings/me returns JSON with correct structure
- [x] POST /api/v4/settings/me creates settings
- [x] POST /api/v4/settings/me updates settings
- [x] POST /api/v4/settings/me returns 400 for invalid JSON
- [x] GET after POST returns updated settings

---

## Sprint2 Procedure QA Minimal Planning (2026-02-20)

### Project: Procedure QA Minimal (Rooted Answers First)

**Goal**: Deliver a minimal F2 backend slice that fixes retrieval/grounding contracts before real Azure integrations.

### Scope
- **Include**: `POST /api/v4/procedure/ask`, retrieval interface, answerer interface, `qa_turns` persistence, rootless-answer prohibition logic
- **Exclude**: Azure AI Search real connection, Azure OpenAI real connection, UI

### Constraints
- TDD-first
- Retriever and answerer start as Fake implementations
- Return fallback when `sources` is empty
- Always return `confidence`, `sources`, and `action_next`

### Success Criteria
- `pytest` passes
- Evidence-backed input returns answer with `sources`
- No-evidence input returns fallback
- Both paths persist to `qa_turns`

### Planned Architecture

```
POST /api/v4/procedure/ask
  -> ProcedureQAService
     -> ProcedureRetrievalService (Fake first)
     -> Rootless guard (if no sources => fallback)
     -> ProcedureAnswererService (Fake first, only when sources exist)
     -> QATurn persistence (feature=procedure_qa)
```

### Planned Deliverables

- Research:
  - `.claude/docs/research/procedure-qa-minimal-codebase.md`
  - `.claude/docs/research/procedure-qa-minimal.md`
  - `.claude/docs/research/procedure-qa-minimal-plan.md`
- Code targets (implementation phase):
  - `app/api/v4/procedure.py`
  - `app/schemas/procedure.py`
  - `app/models/qa_turn.py`
  - `app/services/procedure_retrieval_service.py`
  - `app/services/procedure_answerer_service.py`
  - `app/services/procedure_qa_service.py`

---

## Sprint2 Procedure QA Minimal Implementation (2026-02-20)

### Implemented Scope

- Added `POST /api/v4/procedure/ask`
- Added retrieval service interface + fake implementation
- Added answerer service interface + fake implementation
- Added `qa_turns` persistence model and write path
- Added deterministic rootless-answer prohibition (`sources == []` => fallback)

### Delivered Files

- API
  - `app/api/v4/procedure.py`
  - `app/api/v4/__init__.py` (procedure export)
  - `app/main.py` (router registration)
- Schemas
  - `app/schemas/procedure.py`
  - `app/schemas/__init__.py` (procedure schema exports)
- Models
  - `app/models/qa_turn.py`
  - `app/models/__init__.py` (`QATurn` export)
- Services
  - `app/services/procedure_retrieval_service.py`
  - `app/services/procedure_answerer_service.py`
  - `app/services/procedure_qa_service.py`
  - `app/services/__init__.py` (procedure service exports)
- Tests
  - `tests/api/v4/test_procedure.py`
  - `tests/unit/schemas/test_procedure_schemas.py`
  - `tests/unit/services/test_procedure_qa_service.py`

### Verification Results

- `uv run pytest -q` -> pass (`24 passed`)
- `uv run mypy .` -> pass
- `uv run ty check app/` -> pass
- `uv run ruff check app tests` -> pass
- `uv run ruff check .` -> fail due existing `.claude/hooks` / `.claude/skills` lint debt outside Sprint2 scope

### Outcome

Sprint2 minimal success criteria were met:
- Evidence query returns answer with `sources`
- No-evidence query returns non-empty `fallback`
- `qa_turns` is persisted in both paths
- API contract always includes `confidence`, `sources`, and `action_next`

### Post-Review Hardening (Medium Findings Fixed)

- Added token auth dependency for procedure endpoint (`X-Procedure-Token`).
- Refactored route wiring to dependency-based service injection (no direct fake instantiation in handler body).
- Externalized retrieval/fallback knobs into settings and passed into service constructor.
- Added `query` max-length + blank normalization validation.
- Expanded tests for invalid `lang_mode` and persisted metadata assertions (`citations_json`, `latency_ms`, fallback-path flags).

---

## F2 Procedure QA Real RAG (Fake Replacement) (2026-02-21)

### Implemented Scope

- Replaced procedure retriever runtime from fake implementation to Azure Search-based retrieval (`procedure_index`).
- Replaced procedure answerer runtime from fake implementation to Azure OpenAI-based grounded answer generation.
- Added deterministic `NoopProcedureRetrievalService` for `azure_search_enabled=false` path.
- Added deterministic backend-failure fallback policy for answer generation failures (HTTP 200 + low confidence).
- Kept existing API contract and persistence shape (`qa_turns` with `feature=procedure_qa`) unchanged.

### Delivered Files

- `app/core/config.py`
  - Added `procedure_search_index_name` and `procedure_backend_failure_fallback`.
- `app/services/procedure_retrieval_service.py`
  - Added `ProcedureSearchService`, `AzureProcedureSearchService`,
    `AzureSearchProcedureRetrievalService`, `NoopProcedureRetrievalService`.
- `app/services/procedure_answerer_service.py`
  - Added `AzureOpenAIProcedureAnswererService` and `ProcedureAnswererError`.
- `app/services/procedure_qa_service.py`
  - Added answerer failure handling with deterministic fallback while preserving sources.
- `app/api/v4/procedure.py`
  - Switched DI wiring to runtime services (Azure retrieval/answerer + Noop fallback).
- `app/services/__init__.py`
  - Updated exports to runtime procedure service classes (removed fake exports).
- `tests/api/v4/test_procedure.py`
  - Reworked to dependency-overridden integration tests for success/no-source/answerer-failure and DI wiring.
- `tests/unit/services/test_procedure_qa_service.py`
  - Added answerer-failure fallback persistence test.
- `tests/unit/services/test_procedure_retrieval_service.py`
  - Added Azure retrieval mapping/fallback/failure tests.

### Verification Results

- `uv run ruff check app tests` -> pass
- `uv run pytest -q tests/api/v4/test_procedure.py tests/unit/services/test_procedure_qa_service.py tests/unit/services/test_procedure_retrieval_service.py tests/unit/schemas/test_procedure_schemas.py` -> pass (`19 passed`)
- `uv run mypy app` -> fail (existing cross-module type debt in lecture/speech pipeline; no new procedure-specific errors introduced)

---

## F2 Procedure Index CLI Ingestion (2026-02-21)

### Implemented Scope

- Added non-UI ingestion path to push PDF documents into Azure AI Search `procedure_index`.
- Implemented a standalone CLI script for local/CI use:
  - extract text from PDF
  - chunk and normalize text
  - create/update `procedure_index`
  - upload chunks via `merge_or_upload_documents`
- Added script README with prerequisites, command examples, options, and troubleshooting.

### Delivered Files

- `scripts/procedure_index_ingest/ingest_procedure_pdf.py`
- `scripts/procedure_index_ingest/README.md`

### Verification Results

- `uv run ruff check scripts/procedure_index_ingest/ingest_procedure_pdf.py` -> pass
- `uv run python scripts/procedure_index_ingest/ingest_procedure_pdf.py --help` -> pass

---

## Sprint3 F1 Speech Event Persistence + Subtitle Display Planning (2026-02-20)

### Project: F1 Step 3 (Speech Event Save + Subtitle Display Contract)

**Goal**: Implement SPEC step 3 by adding lecture session start and finalized speech event persistence, with API acknowledgement support for subtitle display continuity.

### Scope

- **Include**:
  - `POST /api/v4/lecture/session/start`
  - `POST /api/v4/lecture/speech/chunk`
  - `lecture_sessions` table/model
  - `speech_events` table/model
  - Validation for consent, active session, timing and confidence ranges
- **Exclude**:
  - OCR ingestion (`/lecture/visual/event`)
  - 30-second summary generation
  - Finalize/index generation flow
  - Frontend implementation
  - Real Azure Speech token issuance

### Planned Architecture

```
POST /api/v4/lecture/session/start
  -> LectureLiveService.start_session()
     -> create LectureSession(status="active")

POST /api/v4/lecture/speech/chunk
  -> LectureLiveService.ingest_speech_chunk()
     -> validate active session + final-event constraints
     -> persist SpeechEvent
     -> return ingestion acknowledgement
```

### Planned Deliverables

- Research:
  - `.claude/docs/research/sprint3-f1-speech-events-and-subtitles-codebase.md`
  - `.claude/docs/research/sprint3-f1-speech-events-and-subtitles.md`
  - `.claude/docs/research/sprint3-f1-speech-events-and-subtitles-plan.md`
- Code targets (implementation phase):
  - `app/api/v4/lecture.py`
  - `app/schemas/lecture.py`
  - `app/models/lecture_session.py`
  - `app/models/speech_event.py`
  - `app/services/lecture_live_service.py`
  - `tests/api/v4/test_lecture.py`
  - `tests/unit/schemas/test_lecture_schemas.py`
  - `tests/unit/services/test_lecture_live_service.py`

---

## Sprint3 F1 Speech Event Persistence + Subtitle Display Implementation (2026-02-20)

### Implemented Scope

- Added `POST /api/v4/lecture/session/start`
- Added `POST /api/v4/lecture/speech/chunk`
- Added `lecture_sessions` persistence model
- Added `speech_events` persistence model
- Added lecture live service for session creation + speech ingestion
- Added schema-level constraints for consent, ROI bounds, timing, confidence, and finalized-event-only ingestion

### Delivered Files

- API
  - `app/api/v4/lecture.py`
  - `app/api/v4/__init__.py` (lecture export)
  - `app/main.py` (lecture router registration)
- Schemas
  - `app/schemas/lecture.py`
  - `app/schemas/__init__.py` (lecture schema exports)
- Models
  - `app/models/lecture_session.py`
  - `app/models/speech_event.py`
  - `app/models/__init__.py` (lecture model exports)
- Services
  - `app/services/lecture_live_service.py`
  - `app/services/__init__.py` (lecture service exports)
- Tests
  - `tests/unit/schemas/test_lecture_schemas.py`
  - `tests/unit/services/test_lecture_live_service.py`
  - `tests/api/v4/test_lecture.py`
  - `tests/conftest.py` (model metadata import updates)
- Shared hardening
  - `app/core/errors.py` (JSON-safe serialization of validation `details`)

### Verification Results

- `uv run ruff check app/models` -> pass
- `uv run ty check app/models` -> pass
- `uv run ruff check app/schemas app/services` -> pass
- `uv run ty check app/schemas app/services` -> pass
- `uv run ruff check app/api/v4 app/main.py` -> pass
- `uv run ty check app/api/v4 app/main.py` -> pass
- `uv run ruff check tests` -> pass
- `uv run ty check tests` -> pass
- `uv run pytest tests/unit/schemas/test_lecture_schemas.py tests/unit/services/test_lecture_live_service.py tests/api/v4/test_lecture.py -v` -> pass (`15 passed`)
- `uv run ty check app/` -> pass
- `uv run pytest -v` -> pass (`42 passed`)
- `uv run ruff check .` -> fail due existing `.claude/hooks` / `.claude/skills` lint debt outside Sprint3 scope
- `uv run ruff format --check .` -> fail due existing `.claude/*` + pre-existing non-Sprint3 files requiring formatting

### Outcome

Sprint3 step-3 success criteria were met:
- Speech events are persisted to `speech_events`.
- Session lifecycle start is persisted to `lecture_sessions`.
- Subtitle-display backend contract is provided via deterministic speech chunk acknowledgement response.
- Scope is kept to step 3 only (no OCR/summary/finalize implementation).

### Post-Review Hardening (High/Medium Findings Fixed)

- Added lecture token auth guard (`X-Lecture-Token`) for all `/api/v4/lecture/*` write endpoints.
- Added request user context dependency (`X-User-Id`) and removed hardcoded service user default.
- Enforced session ownership in ingestion query (`session_id + user_id`) to prevent cross-user writes.
- Added ROI geometry validation (`x1 < x2` and `y1 < y2`) in lecture start schema.
- Added API integration test for inactive-session `409` branch and auth-missing `401` branch.
- Added service test for cross-user session write rejection.
- Re-verified full suite after hardening (`uv run pytest -v` -> `46 passed`).

---

## Azure Provisioning for SIT Copilot MVP (2026-02-20)

### Goal

Provision the minimum Azure resources required by `docs/SPEC.md` section 7 and document a reproducible CLI-based setup path for integration work.

### Provisioned Environment

- Subscription: `Azure サブスクリプション 1`
- Region: `japaneast`
- Resource group: `rg-sitcopilot-dev-02210594`
- Resources:
  - Key Vault: `kvsitc02210594`
  - Storage Account: `stsitc02210594`
  - Azure AI Search: `srchsitc02210594`
  - Azure AI Speech: `speech-sitc-02210594`
  - Azure AI Vision: `vision-sitc-02210594`
  - Azure OpenAI: `aoai-sitc-02210594`
  - Application Insights: `appi-sitc-02210594`

### Provisioning Notes

- Azure resource providers were registered before provisioning:
  - `Microsoft.KeyVault`
  - `Microsoft.CognitiveServices`
  - `Microsoft.Search`
  - `Microsoft.Storage`
  - `Microsoft.Insights`
  - `Microsoft.OperationalInsights`
- Provisioning was executed via Azure CLI from Codex terminal.
- Key Vault was created in RBAC mode; secret write capability was enabled by assigning `Key Vault Secrets Officer` at vault scope.
- Generated local bootstrap file: `.env.azure.generated` (contains connection values and keys for development).
- Stored secrets in Key Vault:
  - `azure-speech-key`
  - `azure-vision-key`
  - `azure-search-key`
  - `azure-storage-key`
  - `azure-openai-key`
  - `applicationinsights-connection-string`
- Removed two failed/empty trial resource groups and retained only the active environment resource group.

### Security and Operations Constraints

- `.env.azure.generated` is sensitive and must not be committed to remote repositories.
- Application runtime should prefer Key Vault and environment-variable injection over hardcoded values.
- Rotate service keys before external demo/release and when sharing environments.

---

## F4 Lecture QA Implementation (2026-02-21)

### Project: F4 Lecture QA (講義後QA)

**Goal**: Implement lecture QA pipeline that answers questions based on actual lecture content (speech, board, slides) with local BM25 search and Azure OpenAI verification.

### Scope
- **Include**:
  - `POST /api/v4/lecture/qa/index/build` - Build BM25 index from SpeechEvents
  - `POST /api/v4/lecture/qa/ask` - Ask question with source-only/source-plus-context modes
  - `POST /api/v4/lecture/qa/followup` - Follow-up questions with context resolution
  - BM25 local search (rank-bm25 library)
  - Azure OpenAI answer generation
  - LLM-based Verifier for citation validation
  - QATurn persistence (feature=lecture_qa)

- **Exclude**:
  - Azure AI Search integration (future F4.3)
  - Real-time OCR integration (handled by F1)

### Module Structure

```
app/
├── api/v4/lecture_qa.py                    # /lecture/qa/index/build, /lecture/qa/ask
├── schemas/lecture_qa.py                   # request/response/citation/index schemas
├── services/
│   ├── lecture_qa_service.py               # Orchestrator: retrieve -> answer -> verify -> persist
│   ├── lecture_retrieval_service.py        # BM25 retrieval + context expansion modes
│   ├── lecture_index_service.py            # Build/rebuild BM25 corpus from SpeechEvent
│   ├── lecture_answerer_service.py         # Azure OpenAI grounded answer generation
│   ├── lecture_verifier_service.py         # Azure OpenAI citation/claim verification
│   ├── lecture_followup_service.py         # Follow-up rewrite + history packing
│   └── lecture_bm25_store.py               # In-memory per-session BM25 cache + locks
└── core/config.py                          # lecture_qa_* and azure_openai_* settings
```

### Data and Pipeline Design

- `LectureSession.qa_index_built` is the canonical DB flag to indicate index availability.
- Index corpus is built from `speech_events` with `is_final=true`, ordered by `start_ms`.
- Primary source unit is one `SpeechEvent` row (`chunk_id = speech_event.id`), preserving timestamp precision for citations.
- Retrieval modes:
  - `source-only`: return top-k matched chunks only.
  - `source-plus-context`: expand each hit with neighboring chunks (window by chunk-count or milliseconds), deduplicate by `chunk_id`, and mark which chunk is the direct hit.
- QA turn history is persisted in existing `qa_turns` table with `feature=lecture_qa`.

### API Contract (v4)

- `POST /api/v4/lecture/qa/index/build`
  - Ensures ownership (`session_id + user_id`), builds/rebuilds BM25 index, sets `qa_index_built=true`.
- `POST /api/v4/lecture/qa/ask`
  - Performs follow-up resolution, retrieval, answering, verification, and history persistence.
  - Supports `retrieval_mode` = `source-only | source-plus-context`.

### Verification Guardrails

- If retrieval returns no chunks: deterministic low-confidence fallback (no hallucinated answer).
- Verifier validates each cited claim against provided source snippets.
- If verifier rejects support:
  - First pass: attempt constrained repair (answer only from verified chunks).
  - If still unsupported: return fallback with low confidence and keep rejected citations out of response.

### Async/Concurrency

- `rank-bm25` scoring/index construction is CPU-bound and must run via `asyncio.to_thread(...)`.
- Per-session `asyncio.Lock` prevents concurrent index-build races.
- DB IO remains async via SQLAlchemy 2.0 `AsyncSession`; long-running LLM calls are timeout-bound.

---

## Implementation Plan

### Patterns & Approaches

| Pattern | Purpose | Notes |
|---------|---------|-------|
| Agent Teams | Parallel work with inter-agent communication | /startproject, /team-implement, /team-review |
| Subagents | Isolated tasks returning results | External research, Codex consultation, implementation |
| Skill Pipeline | `/startproject` → `/team-implement` → `/team-review` | Separation of concerns across skills |

### Libraries & Roles

| Library | Role | Version | Notes |
|---------|------|---------|-------|
| Codex CLI | Planning, design, complex code | gpt-5.3-codex | Architecture, planning, debug, complex implementation |
| Gemini CLI | Multimodal file reading | gemini-3-pro | PDF/video/audio/image extraction ONLY |
| FastAPI | Web framework | >=0.115 | Async-first, type-safe |
| pytest | Testing | >=8.0 | TDD with async support |
| httpx | Async HTTP client | >=0.28 | For testing FastAPI with ASGITransport |

### Key Decisions

| Decision | Rationale | Alternatives Considered | Date |
|----------|-----------|------------------------|------|
| Gemini role expanded to codebase analysis + research + multimodal | Gemini CLI has native 1M context; Claude Code is 200K; delegate large-context tasks to Gemini | Keep Claude for codebase analysis (requires 1M Beta) | 2026-02-19 |
| All subagents default to Opus | 200K context makes quality of reasoning more important than context size; Opus provides better output | Sonnet (cheaper but 200K same as Opus, weaker reasoning) | 2026-02-19 |
| Agent Teams default model changed to Opus | Consistent with subagent model selection; better reasoning for parallel tasks | Sonnet (cheaper) | 2026-02-19 |
| Claude Code context corrected to 200K | 1M is Beta/pay-as-you-go only; most users have 200K; design must work for common case | Assume 1M (only works for Tier 4+ users) | 2026-02-19 |
| Subagent delegation threshold lowered to ~20 lines | 200K context requires more aggressive context management | 50 lines (was based on 1M assumption) | 2026-02-19 |
| Codex role unchanged (planning + complex code) | Codex excels at deep reasoning for both design and implementation | Keep Codex advisory-only | 2026-02-17 |
| Codex project skills include startproject/team-implement/team-review bridges | Enables Claude-style `/startproject`, `/team-implement`, `/team-review` workflow from Codex while keeping `.claude/skills/*` as source of truth | Duplicate full skill content under `.codex/skills`, keep commands Claude-only | 2026-02-20 |
| Codex project skills include checkpointing bridge plus `/checkpoining` alias | Enables session checkpoint workflow from Codex and keeps typo-tolerant command compatibility while reusing `.claude/skills/checkpointing` as source of truth | Keep checkpointing Claude-only, no alias support | 2026-02-20 |
| Codex skills rewritten to remove Claude runtime dependencies | Ensures `/startproject`, `/team-implement`, `/team-review`, `/checkpointing` can run with Codex + Gemini only (no Agent Teams, Task tool, subagents) | Keep bridge-only delegation to `.claude/skills/*` | 2026-02-20 |
| /startproject split into 3 skills | Separation of Plan/Implement/Review gives user control gates | Single monolithic skill | 2026-02-08 |
| Agent Teams for Research ↔ Design | Bidirectional communication enables iterative refinement | Sequential subagents (old approach) | 2026-02-08 |
| Agent Teams for parallel implementation | Module-based ownership avoids file conflicts | Single-agent sequential implementation | 2026-02-08 |
| FastAPI AsyncClient for testing (2025) | httpx.AsyncClient with ASGITransport is modern best practice for async FastAPI tests | TestClient (legacy), starlette TestClient | 2026-02-21 |
| API versioning with /api/v4/ | Explicit versioning allows breaking changes without breaking existing clients | /api/v1/ (arbitrary), no versioning (brittle) | 2026-02-21 |
| Layered architecture: API → Service → Repository | Clear separation of concerns enables independent testing and evolution | Flat structure (harder to scale), MVC (less clear for APIs) | 2026-02-21 |
| User settings persisted in SQLite with JSON column | Flexible, schema-less user preferences while keeping one row per user; SQLite JSON functions remain available | Normalized key-value table (more joins), TEXT blob without JSON type | 2026-02-20 |
| SQLAlchemy 2.0 async stack for DB access | Matches FastAPI async flow and keeps one consistent ORM access pattern | Sync SQLAlchemy (thread pool overhead), raw sqlite3 (less abstraction) | 2026-02-20 |
| Settings API boundary: API → Service (upsert/get) | Keeps HTTP details out of business logic and enables isolated unit tests for settings behavior | Direct DB calls in route handlers | 2026-02-20 |
| Settings upsert creates missing `users` row lazily | Keeps router thin and guarantees `users` + `user_settings` consistency in demo single-replica SQLite without separate signup flow | Require pre-provisioned user row before POST `/settings/me` | 2026-02-20 |
| Validation errors normalized to common 400 schema | Aligns API with project-wide error contract and success criteria (`400` for invalid input with structured `error` payload) | Keep FastAPI default 422 `detail` response | 2026-02-20 |
| Prioritize F2 Procedure QA as the next feature after backend/settings foundation | Matches `docs/SPEC.md` implementation order step 2 and enables an early source-grounded demo path before higher-latency F1 realtime pipelines | Start F1 speech/OCR ingestion first | 2026-02-20 |
| Sprint2 starts with fake retriever/answerer interfaces before Azure wiring | Freezes RAG boundaries and response contract early, while keeping implementation deterministic for TDD | Implement real Azure integrations first (higher coupling and slower tests) | 2026-02-20 |
| Procedure rootless answers are blocked by deterministic guard (`sources == []` => fallback) | Enforces evidence-first safety rule from spec and prevents unsupported answers in MVP | Allow answerer output without sources and trust model self-restraint | 2026-02-20 |
| Procedure QA persistence uses shared `qa_turns` with `feature=procedure_qa` and serialized `sources` | Keeps lecture/procedure QA telemetry unified and future verifier compatibility intact | Separate procedure-specific history table | 2026-02-20 |
| Procedure endpoint enforces header token auth and DI-based service composition | Addresses review findings by reducing anonymous write risk and avoiding route-level implementation coupling | Keep route-level fake service instantiation and no auth in minimal mode | 2026-02-20 |
| Procedure query limits and fallback/retrieval knobs are settings-driven | Improves operational tunability and protects against unbounded payload growth | Keep hardcoded literals in service and schema | 2026-02-20 |
| Procedure QA runtime switched from fake adapters to Azure Search (`procedure_index`) + Azure OpenAI, with deterministic `HTTP 200` fallback on backend errors | Preserves response contract and demo continuity while enabling real retrieval/generation path | Return 503 on backend failures or keep fake runtime adapters | 2026-02-21 |
| Procedure document ingestion is standardized as CLI-based PDF → chunk → `procedure_index` upload (no Azure Portal dependency) | Makes RAG knowledge updates reproducible in local/CI flows and reduces operational variance | Manual Azure Portal import/indexer-only operation | 2026-02-21 |
| Sprint3 F1 is backend-first and persists finalized subtitle events only | Aligns with SPEC (frontend displays partial subtitles, backend stores finalized events) and keeps ingestion deterministic | Persist partial + final events together in Sprint3 | 2026-02-20 |
| Sprint3 endpoint scope is limited to session start + speech chunk | Matches implementation order step 3 and avoids coupling to OCR/summary/finalize before contracts are stable | Build full F1 pipeline in one sprint | 2026-02-20 |
| Subtitle display support is defined as ingestion acknowledgement contract in backend | Repository currently has no frontend code; acknowledgement keeps client rendering decoupled while preserving DB traceability | Add subtitle polling/read endpoint in Sprint3 | 2026-02-20 |
| Validation error details are JSON-encoded before error response serialization | Prevents `ValueError` objects inside Pydantic `ctx` from breaking error response generation | Keep raw `exc.errors()` payload | 2026-02-20 |
| Lecture write endpoints require token auth and user context headers | Fixes high-risk anonymous write surface and prepares multi-user ownership boundary | Keep lecture endpoints unauthenticated in Sprint3 | 2026-02-20 |
| Lecture speech ingestion checks session ownership (`session_id + user_id`) | Prevents cross-user session write contamination in shared environments | Query by `session_id` only | 2026-02-20 |
| Lecture ROI validation enforces geometry ordering | Prevents invalid inverted regions from propagating to downstream OCR pipeline | Validate non-negative coordinates only | 2026-02-20 |
| Lecture QA uses `SpeechEvent` rows as BM25 chunk units and keeps index in process-local cache keyed by `session_id` | Reuses finalized subtitle data without schema churn and keeps retrieval latency low for active sessions | Persist separate lecture chunk index tables first | 2026-02-20 |
| Lecture QA keeps existing orchestration pattern (`retrieve -> answer -> verify`) with Azure OpenAI for answering and citation validation | Aligns with procedure QA structure and adds explicit groundedness gate before response | Single-pass answer generation without verifier step | 2026-02-20 |
| Lecture follow-up handling rewrites question to standalone query using recent `QATurn` context before retrieval | Improves retrieval recall for pronoun/ellipsis follow-ups while keeping source grounding explicit | Retrieve directly on raw follow-up question only | 2026-02-20 |
| Azure MVP resources are provisioned via CLI in `japaneast` with low-cost/default SKUs (`Speech F0`, `ComputerVision F0`, `Search free`, `OpenAI S0`) | Unblocks integration quickly while controlling cost and preserving reproducibility | Manual portal-only setup per developer | 2026-02-20 |
| Azure secrets are stored in Key Vault and mirrored to local `.env.azure.generated` for bootstrap | Keeps a secure central source while enabling immediate local integration testing | Local `.env` only, or Key Vault-only with full managed identity wiring first | 2026-02-20 |
| Key Vault secret operations use RBAC role assignment (`Key Vault Secrets Officer`) | Vault was created in RBAC mode; role assignment is the compatible path for secret writes | Recreate vault in access-policy mode | 2026-02-20 |

---

## Frontend Architecture (2026-02-21)

### Project: React 18 + TypeScript Frontend for SIT Copilot

**Goal**: Create an accessible, real-time lecture assistance frontend that integrates with the existing FastAPI backend.

### Tech Stack

| Category | Technology | Rationale |
|----------|------------|-----------|
| Framework | React 18 + TypeScript | Industry standard, strong ecosystem, type safety |
| Build | Vite | Fast HMR, optimized builds, native ESM |
| Styling | Tailwind CSS | Utility-first, matches design token system |
| Components | shadcn/ui + Radix UI | Accessible primitives, customizable, headless |
| Data Fetching | TanStack Query | Server state management, caching, background refetches |
| Virtualization | TanStack Virtual | Efficient transcript rendering (thousands of lines) |
| Tables | TanStack Table | Sortable/filterable source lists |
| State | Zustand | Lightweight for ephemeral UI state (panel mode, autoscroll, stream lag) |
| Routing | react-router | Declarative routing, nested routes |
| Forms | react-hook-form + zod | Type-safe form validation |
| i18n | i18next | Japanese/English localization |
| Animation | Framer Motion | Accessible motion (respects prefers-reduced-motion) |
| Real-time | WebSocket (Native) | Live transcript/streaming with SSE fallback |

### Project Structure

```
sit-copilot/
├── app/                          # Existing FastAPI backend
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── providers/        # QueryProvider, I18nProvider, ThemeProvider, A11yProvider
│   │   │   ├── router/
│   │   │   │   ├── index.tsx     # react-router config
│   │   │   │   └── guards.tsx    # Auth guards, live session guards
│   │   │   └── AppShell.tsx      # TopBar, live region, toast container
│   │   ├── pages/
│   │   │   ├── LandingPage.tsx               # /
│   │   │   ├── LectureListPage.tsx           # /lectures
│   │   │   ├── LectureLivePage.tsx           # /lectures/:id/live
│   │   │   ├── LectureReviewPage.tsx         # /lectures/:id/review
│   │   │   ├── LectureSourcesPage.tsx        # /lectures/:id/sources
│   │   │   ├── SettingsSheetRoute.tsx        # /settings
│   │   │   └── OperatorSessionPage.tsx       # /operator/session
│   │   ├── features/
│   │   │   ├── lectures/                     # Lecture card, list, filters
│   │   │   ├── live-transcript/              # TanStack Virtual list + live region
│   │   │   ├── live-sources/                 # Source frame cards, OCR display
│   │   │   ├── live-assist/                  # Status pills, key terms, QA chips
│   │   │   ├── review-qa/                    # QA input, streaming answer, citation chips
│   │   │   ├── settings/                     # Settings form, LocalStorage sync
│   │   │   └── operator/                     # Demo operator controls
│   │   ├── components/
│   │   │   ├── ui/                           # shadcn/ui generated components
│   │   │   ├── common/                       # AppShell, EmptyState, Skeleton, ErrorBoundary
│   │   │   ├── feedback/                     # Toast, InlineMessage, LiveStatusPill
│   │   │   └── a11y/                         # LiveRegionAnnouncer, FocusTrap, SkipLink
│   │   ├── lib/
│   │   │   ├── api/                          # baseClient, query keys, endpoint adapters
│   │   │   ├── stream/                       # WS/SSE client, reconnect state machine
│   │   │   ├── i18n/                         # i18next config, ja/en namespaces
│   │   │   ├── forms/                        # react-hook-form schemas, validators
│   │   │   └── utils/                        # formatters, cn(), date/intl helpers
│   │   ├── stores/                           # Zustand slices (ephemeral UI/session state)
│   │   │   ├── liveSession.ts                # Connection state, panel mode, autoscroll
│   │   │   ├── settings.ts                   # Theme, language, reduced motion
│   │   │   └── transcript.ts                 # Virtual list state, scroll position
│   │   ├── styles/
│   │   │   ├── tokens.css                    # Design tokens (CSS variables)
│   │   │   └── globals.css                   # Global styles, Tailwind directives
│   │   ├── locales/
│   │   │   ├── ja/                           # Japanese translations
│   │   │   └── en/                           # English translations
│   │   └── types/
│   │       ├── lecture.ts                    # Lecture domain types
│   │       ├── transcript.ts                 # Transcript types
│   │       ├── qa.ts                         # QA domain types
│   │       └── api.ts                        # API response types
│   ├── staticwebapp.config.json              # Azure SWA config
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── components.json                       # shadcn config
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   └── package.json
└── .claude/docs/DESIGN.md
```

### Key Architectural Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Monorepo + `frontend/` directory** | API/UI contract co-evolution, single CI/CD visibility, shared docs |
| 2 | **API client via `/api` facade** | Frontend calls `/api/*`; dev proxy rewrites to `/api/v4/*`; Azure SWA handles production routing |
| 3 | **Typed stream boundary** | `StreamClient` abstraction with WebSocket-first and SSE fallback behind same event interface |
| 4 | **Reconnect state machine** | Bounded backoff (1s/2s/5s/10s), heartbeat, resumable subscription; exposes `connecting/live/reconnecting/degraded/error` to UI |
| 5 | **State split: TanStack Query for server, Zustand for ephemeral** | TanStack Query handles caching/invalidation; Zustand holds transient UI state (panel mode, autoscroll, stream lag) |
| 6 | **Hybrid `pages/` + `features/` structure** | Routes stay thin in `pages/`; feature modules in `features/` own hooks/components/store/types |
| 7 | **Cross-cutting foundations first** | WCAG 2.2 AA (live regions, focus, keyboard), i18n (ja/en), token-driven themes (light/dark/high-contrast), transcript virtualization |

### API Client Architecture

```typescript
// lib/api/baseClient.ts
import axios from 'axios';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Auth interceptor (will be wired to real auth)
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

### TanStack Query Configuration

```typescript
// app/providers/QueryProvider.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 minute
      gcTime: 1000 * 60 * 5, // 5 minutes (formerly cacheTime)
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        // Don't retry 4xx errors
        if (error && 'status' in error && typeof error.status === 'number') {
          return error.status >= 500 && failureCount < 3;
        }
        return failureCount < 3;
      },
    },
  },
});
```

### WebSocket Stream Architecture

```typescript
// lib/stream/StreamClient.ts
type ConnectionState = 'idle' | 'connecting' | 'live' | 'reconnecting' | 'degraded' | 'error';

interface StreamClientConfig {
  wsUrl: string;
  heartbeatInterval: number;
  reconnectDelays: number[]; // [1000, 2000, 5000, 10000]
}

class StreamClient {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;

  connect(sessionId: string): void {
    // Connect, send subscription message, start heartbeat
  }

  disconnect(): void {
    // Clean close, cancel timers
  }

  on<Event>(event: Event, handler: (payload: any) => void): Unsubscribe {
    // Event subscription
  }
}
```

### Domain Types

```typescript
// types/lecture.ts
export type LangMode = 'ja' | 'easy-ja' | 'en';
export type ThemeMode = 'light' | 'dark' | 'high-contrast';
export type LectureStatus = 'upcoming' | 'live' | 'ended';

export interface LectureListItem {
  id: string;
  courseName: string;
  instructor: string;
  room: string;
  startAt: string; // ISO 8601
  endAt: string;
  status: LectureStatus;
  langMode: LangMode;
  accessibilityTags: string[];
}

// types/transcript.ts
export interface TranscriptLine {
  eventId: string;
  sessionId: string;
  startMs: number;
  endMs: number;
  text: string;
  translatedText?: string;
  confidence: number;
  speaker: 'teacher' | 'unknown';
  isFinal: boolean;
}

// types/qa.ts
export interface LectureSource {
  chunk_id: string;
  type: 'speech' | 'visual';
  text: string;
  timestamp?: string;
  start_ms?: number;
  end_ms?: number;
  speaker?: string;
  bm25_score: number;
  is_direct_hit: boolean;
}

export interface LectureAskResponse {
  answer: string;
  confidence: 'high' | 'medium' | 'low';
  sources: LectureSource[];
  verification_summary?: string;
  action_next: string;
  fallback?: string;
}
```

### Design Token Integration

```css
/* styles/tokens.css */
:root {
  /* color - light theme defaults */
  --bg-page: 248 250 252;
  --bg-surface: 255 255 255;
  --bg-muted: 241 245 249;
  --fg-primary: 15 23 42;
  --fg-secondary: 71 85 105;
  --accent: 37 99 235;

  /* radius */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;

  /* spacing (4px base scale) */
  --sp-1: 4px;
  --sp-2: 8px;
  --sp-3: 12px;
  --sp-4: 16px;
  --sp-6: 24px;

  /* motion */
  --dur-fast: 120ms;
  --dur-base: 180ms;
  --ease-standard: cubic-bezier(0.2, 0, 0, 1);
}

[data-theme="dark"] {
  --bg-page: 15 23 42;
  --bg-surface: 30 41 59;
  --fg-primary: 248 250 252;
}

[data-theme="high-contrast"] {
  --bg-page: 0 0 0;
  --bg-surface: 0 0 0;
  --fg-primary: 255 255 255;
  --accent: 255 255 255;
}
```

### Accessibility Strategy

1. **Live Regions**: `AppShell` contains a visually-hidden `div` with `aria-live="polite"` for status announcements
2. **Focus Management**: `useFocusTrap` hook for modals/side-sheets; `useRestoreFocus` for returning focus after close
3. **Keyboard Navigation**: All interactive elements are keyboard-accessible; Arrow keys for tabs/lists
4. **Reduced Motion**: `useReducedMotion()` hook; Framer Motion respects `prefers-reduced-motion`
5. **Screen Reader**: Semantic HTML; ARIA labels on icon-only buttons; descriptive link text

### Implementation Roadmap

| Step | Deliverable | Dependencies |
|------|-------------|--------------|
| 1 | Create `frontend/` app (Vite+React+TS), path aliases, lint/test base | None |
| 2 | Add Tailwind + shadcn/ui + Radix setup | 1 |
| 3 | Add design tokens + theme engine (light/dark/high-contrast) | 2 |
| 4 | Add i18next (`ja/en`) and translation namespace structure | 1 |
| 5 | Build API layer (`baseClient`, auth headers, query key factory, QueryClient defaults) | 1 |
| 6 | Build Stream layer (`StreamClient`, WS adapter, SSE fallback, reconnect policy) | 5 |
| 7 | Configure router + all route shells + settings side-sheet route behavior | 1, 4 |
| 8 | Implement lecture list/sources/review pages with TanStack Query/Table | 5, 7 |
| 9 | Implement live lecture page (3 panels, virtual transcript, live regions, keyboard nav) | 6, 7 |
| 10 | Azure SWA deploy config, env strategy, a11y/perf tests, operator page hardening | 3, 8, 9 |

### Development Workflow

```bash
# Install dependencies
cd frontend && uv sync  # or npm install

# Dev server with API proxy
npm run dev  # Vite proxies /api -> http://localhost:8000/api/v4

# Type check
npm run type-check

# Lint
npm run lint

# Test
npm run test

# Build for production
npm run build
```

### Azure Static Web Apps Configuration

```json
{
  "platform": "node",
  "appName": "sit-copilot-frontend",
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "api": "app/main.py",
  "routes": [
    { "route": "/api/*", "methods": ["GET", "POST", "PUT", "DELETE"], "allowedRoles": ["anonymous"] },
    { "route": "/*", "rewrite": "/index.html" }
  ]
}
```

### Frontend Key Decisions

| Decision | Rationale | Date |
|----------|-----------|------|
| Monorepo structure with `frontend/` directory | Single repository simplifies API/UI contract evolution and CI/CD | 2026-02-21 |
| API facade with `/api` prefix in frontend | Dev proxy rewrites to `/api/v4/*`; production routing handled by Azure SWA | 2026-02-21 |
| WebSocket-first with SSE fallback for live streams | WebSocket provides bidirectional low-latency communication; SSE as fallback for restrictive networks | 2026-02-21 |
| TanStack Query for server state, Zustand for ephemeral UI state | Clear separation: Query handles caching/invalidation; Zustand holds transient state | 2026-02-21 |
| shadcn/ui + Radix UI for component primitives | Accessible, unstyled components that can be customized via Tailwind and design tokens | 2026-02-21 |
| TanStack Virtual for transcript list | Handles thousands of transcript lines without performance degradation | 2026-02-21 |
| Design tokens via CSS variables | Enables theme switching (light/dark/high-contrast) without rebuilding CSS | 2026-02-21 |
| i18next for Japanese/English localization | Industry standard with namespace support and interpolation | 2026-02-21 |
| Remove login-first UX for MVP demo and use single demo-start CTA | Keeps demo flow simple and aligns with no-SSO policy in MVP scope | 2026-02-21 |
| Frontend API auth uses fixed demo headers with env overrides (`X-Lecture-Token`, `X-User-Id`) | Allows login-free real API calls without backend changes while keeping deployment-configurable secrets | 2026-02-21 |
| SSE stream client uses fetch-based parser with custom headers | Native `EventSource` cannot send required auth headers; fetch-stream keeps existing token contract | 2026-02-21 |
| Live page sends pseudo transcript chunks to `/api/v4/lecture/speech/chunk` until STT integration lands | Enables real backend-driven stream updates today while preserving transport/API contracts | 2026-02-21 |
| Lecture list becomes session-driven (`session/start` + localStorage) instead of non-existent `/lectures` API | Removes contract mismatch and keeps demo sessions reproducible in browser without backend list endpoint | 2026-02-21 |
| UI language switching uses immediate `i18n.changeLanguage` + merged settings auto-persist with non-blocking local fallback on save failure | Prevents perceived language-switch breakage, preserves existing settings fields, and keeps UI responsive for international students even under API failures | 2026-02-24 |

---

## Azure OpenAI Integration for RAG (2026-02-22)

### Overview

Configured Azure OpenAI Service (Cognitive Services - Japan East region) for RAG answer generation and verification. The integration includes graceful error handling that falls back to local grounded responses when Azure OpenAI is unavailable.

### Configuration

| Setting | Value | Notes |
|----------|-------|-------|
| **API Key** | `<SET_IN_KEY_VAULT>` | Stored in `.env.azure.generated` |
| **Endpoint** | `https://aoai-sitc-02210594.cognitiveservices.azure.com` | Azure OpenAI endpoint |
| **Account Name** | `aoai-sitc-02210594` | Resource identifier |
| **Model** | `gpt-5-nano` | Deployment name in Azure OpenAI |
| **API Version** | `2024-05-01-preview` | Required for Cognitive Services compatibility |
| **Enabled** | `true` | Controlled via `AZURE_OPENAI_ENABLED` |

### Key Implementation Details

**URL Construction for Cognitive Services:**
```
{endpoint}/openai/deployments/{model}/chat/completions?api-version={api_version}
```

Example:
```
https://aoai-sitc-02210594.cognitiveservices.azure.com/openai/deployments/gpt-5-nano/chat/completions?api-version=2024-05-01-preview
```

**Error Handling Pattern:**
```python
try:
    draft = await self._answerer.answer(...)
except LectureAnswererError:
    response = self._build_local_grounded_response(sources=sources)
    # Returns HTTP 200 with low confidence, preserving sources
```

**Configuration Files:**
- `.env.azure.generated` - Environment variables (gitignored)
- `.env.azure.generated.template` - Template for setup
- `app/core/config.py` - Settings schema with `azure_openai_api_version`

### API Version Compatibility

| Component | API Version | Status |
|-----------|-------------|--------|
| Chat Completions | `2024-02-15-preview` | ✅ Working |
| Default (`2024-10-21`) | `2024-10-21` | ⚠️ DeploymentNotFound error |

### Key Decisions

| Decision | Rationale | Date |
|----------|-----------|------|
| Use `2024-02-15-preview` API version | Required for Cognitive Services endpoints; later versions return `DeploymentNotFound` | 2026-02-22 |
| Add `azure_openai_api_version` to settings schema | Allows per-environment API version configuration | 2026-02-22 |
| Pass `api_version` parameter to all Azure OpenAI services | Ensures consistent API version across answerer, verifier, and followup services | 2026-02-22 |
| Graceful degradation on network errors | Returns HTTP 200 with local fallback instead of HTTP 503 | 2026-02-22 |
| Region-based endpoint format | `https://japaneast.api.cognitive.microsoft.com` for Japan East region | 2026-02-22 |

### Error Handling Improvements

**Before:**
- Azure OpenAI failure → HTTP 503 Service Unavailable
- User sees error message

**After:**
- Azure OpenAI failure → HTTP 200 OK with local grounded response
- Low confidence, sources preserved
- Verification summary indicates fallback occurred

### Testing Results

✅ **Test Case**: "機械学習とは何ですか？"
- Retrieved 2 relevant sources from lecture
- Azure OpenAI generated answer with timestamps
- Verified all claims are grounded in sources
- HTTP 200 response with confidence=low (calculation issue)

### Azure CLI Setup for Development

**Tool Installation:**
```bash
# Install Azure CLI via uv (Python 3.10 compatible)
UV_PYTHON=/usr/bin/python3.10 uv tool install azure-cli
```

**Commands Used:**
```bash
# Login
uv tool run azure-cli az login

# List resources
az cognitiveservices account list --query "[?kind=='OpenAI']"

# Get API keys
az cognitiveservices account keys list \
  --name "aoai-sitc-02210594" \
  --resource-group "rg-sitcopilot-dev-02210594"

# List deployments
az cognitiveservices account deployment list \
  --name "aoai-sitc-02210594" \
  --resource-group "rg-sitcopilot-dev-02210594"
```

**Patched Wrapper for Python 3.10:**
```bash
/tmp/run_az.sh
```
Applies patches for:
- `time.clock()` → `time.perf_counter()`
- `collections.Iterable` → `collections.abc.Iterable`

### Documentation Updates

- ✅ `CLAUDE.md` - Updated Azure OpenAI constraints
- ✅ `.claude/docs/DESIGN.md` - This section
- ✅ `.env.azure.generated.template` - Configuration template
- ✅ `AZURE_SETUP_GUIDE.md` - Comprehensive setup guide
- ⚠️ `.env.azure.generated.example` - Permission denied (use template instead)

### Security Notes

⚠️ **Important**: `.env.azure.generated` contains sensitive API keys.
- File is gitignored via `.gitignore`
- Never commit API keys to repository
- Rotate keys if compromised
- Use Key Vault for production deployments
| Settings sync contract fixed to `GET/POST /api/v4/settings/me` with `{settings: ...}` envelope | Matches backend schema and avoids method/path mismatch (`PUT` removal) | 2026-02-21 |

---

## WandB Weave Observer Architecture (2026-02-22)

### Overview

Introduce Protocol-based observer integration for lecture flows so that LLM calls, QA orchestration, OCR, and summary generation are traced without affecting request success paths.

### Architecture

```
FastAPI Route (Depends)
  -> Observed*Service wrappers (QA / Answerer / Summary / OCR / Live / Finalize)
      -> Existing core services (SqlAlchemy*, AzureOpenAI*, AzureVision*)
      -> WeaveObserverService (Protocol)
            -> Async observer dispatcher (queue + background workers)
                  -> Weave client adapter
                        -> Local mode (dev) or Cloud mode (prod)
```

### Key Decisions

| Decision | Rationale | Date |
|----------|-----------|------|
| Use `WeaveObserverService` Protocol + wrapper decorators | Matches existing service architecture and keeps business logic clean | 2026-02-22 |
| Provide `NoopWeaveObserverService` and `UnavailableWeaveObserverService` | Follows existing Noop/fail-safe patterns and keeps behavior deterministic | 2026-02-22 |
| Observer dispatch is fire-and-forget (`create_task`) with bounded queue | Observer failures/latency must never block API flow | 2026-02-22 |
| Build session trace hierarchy using `session_id` as stable trace key | Enables cross-request trace continuity from lecture start to end | 2026-02-22 |
| Capture prompt/response behind dedicated flags + truncation controls | Meets observability requirements while controlling payload size/privacy risk | 2026-02-22 |

### Implementation Plan

1. Add observer modules:
   - `app/services/observability/weave_observer_service.py`
   - `app/services/observability/weave_dispatcher.py`
   - `app/services/observability/weave_context.py`
2. Add wrappers:
   - `ObservedLectureQAService`
   - `ObservedLectureAnswererService`
   - `ObservedLectureSummaryService`
   - `ObservedLectureSummaryGeneratorService`
   - `ObservedVisionOCRService`
   - `ObservedLectureLiveService`
   - `ObservedLectureFinalizeService`
3. Add settings in `app/core/config.py`:
   - `weave_observer_enabled`
   - `weave_mode` (`local` / `cloud`)
   - `weave_project`, `weave_entity`
   - `weave_capture_prompts`, `weave_capture_responses`
   - queue/timeout tuning fields
4. Initialize in `app/main.py` lifespan:
   - startup: create/start observer and store singleton handle
   - shutdown: drain queue with timeout and close observer client
5. Wire dependencies in `app/api/v4/lecture.py` and `app/api/v4/lecture_qa.py` so providers return observed wrappers.

### Trace Structure

- Trace root: `lecture.session` (keyed by `session_id`)
- Child spans:
  - `lecture.start`
  - `qa.ask` / `qa.followup`
    - `retrieval.search`
    - `llm.answer.generate`
    - `verifier.verify`
    - `verifier.repair` (optional)
  - `summary.latest` / `summary.rebuild`
    - `llm.summary.generate`
  - `ocr.extract_text`
  - `lecture.end`

### Testing Strategy (TDD)

1. Unit tests for observer config/factory fallback behavior.
2. Unit tests for dispatcher non-blocking guarantees (queue full, timeout, exceptions).
3. Unit tests for each observed wrapper (success/error paths, attributes, latency capture).
4. API tests verifying feature-flag dependency wiring in `lecture.py` / `lecture_qa.py`.
5. Integration test with in-memory observer sink for full session flow:
   `start -> ask/followup -> summary -> finalize`.

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Observer queue overflow under burst traffic | Bounded queue + drop policy + dropped-count metric |
| Sensitive prompt/response leakage | Default capture off in prod; explicit flags and truncation |
| SDK/network instability | Worker-level timeout, retry budget, and silent isolation from request path |
| Multi-instance trace continuity gaps | Stable `session_id` trace key and explicit trace attributes |

### Async Integration Risk Matrix (2026-02-22)

| Risk | Likelihood | Impact | Concrete Mitigation |
|------|------------|--------|---------------------|
| Performance overhead (`@weave.op` wrapping, payload serialization, cloud publish latency) | Medium | High | Keep observer off request critical path (`put_nowait` to bounded async queue), initialize Weave once at startup, run any sync SDK calls via worker/threadpool, and sample/truncate payload fields by default. |
| Memory leaks (unclosed spans, never-drained queue, orphan background tasks) | Medium | High | Enforce `try/finally` span closing, track worker tasks and remove on completion, cap queue size with explicit drop policy, and add lifespan shutdown hooks to flush with timeout then cancel workers. |
| Error isolation failure (observer exceptions bubbling into business flow) | Medium | High | Wrap all observer writes in broad `try/except`, never re-raise from observer layer, add `NoopWeaveObserverService` fallback + circuit-breaker disable flag after repeated failures, and expose health counters for disabled/dropped events. |
| Azure deployment mismatch (egress limits, auth, env drift across slots) | High | High | Store `WANDB_API_KEY` in Key Vault (not env files), use Managed Identity to resolve secrets at startup, validate required Weave/Azure settings on boot, and degrade to Noop mode when Weave connectivity/auth fails. |
| Testing complexity (async timing, background worker behavior, SDK mocking) | High | Medium | Use Protocol-based fake observer + in-memory sink for unit tests, add failure-injection tests (timeout/network/queue-full), ensure `pytest-asyncio` cleanup of worker tasks per test, and run one integration test with real queue + fake transport. |
| Data privacy leakage (PII in prompts/responses and trace attributes) | High | High | Default `capture_prompts/responses=false` in production, apply allowlist-based payload capture, redact known PII patterns before enqueue, hash user/session identifiers, and define retention/deletion policy aligned to compliance requirements. |

## Live Subtitle Transform Fallback Signaling (2026-02-23)

### Decision Summary

- Expanded live subtitle transform contract to structured output:
  - `transformed_text`
  - `status` (`translated` | `fallback` | `passthrough`)
  - `fallback_reason` (nullable)
- Updated caption transform service to return structured result and reason-coded fallback states instead of opaque string-only output.
- Added `reasoning_effort: "minimal"` for GPT-5 deployments in subtitle transform requests to reduce empty completion behavior.
- Preserved local glossary fallback for `en` / `easy-ja`, but now expose fallback usage explicitly to frontend.
- Frontend live transcript now:
  - applies fallback text as display output
  - shows throttled warning toast on fallback
  - keeps a persistent "翻訳フォールバック中" badge in transcript header until language reset.
- Added frontend runtime compatibility normalization for `/subtitle/transform`:
  - if `status` is missing/invalid, infer `translated` only when output is non-empty and differs from source
  - otherwise force `fallback` with `fallback_reason=missing_transform_status` to avoid silent Japanese lock-in.

### Rationale

- Users previously saw Japanese text in non-Japanese views with no explanation, making language switch appear broken.
- Explicit fallback signaling keeps live UX continuous while making degradation observable and debuggable.
- Structured API response keeps backward compatibility (`transformed_text` retained) while enabling richer client behavior.

### Compatibility Rules

- `/api/v4/lecture/subtitle/transform` must keep existing fields and append new status metadata; do not remove `transformed_text`.
- Fallback status must not block subtitle rendering; it is a quality signal, not a hard error.
- This change is scoped to subtitle transform flow only; other Azure OpenAI feature paths remain unchanged.
- Frontend must treat malformed transform metadata (`status` missing/invalid or translated+empty text) as fallback-safe behavior.

### Changelog

- 2026-02-24: Added frontend UI-language implementation decision (immediate switch + merged auto-persist + local fallback) and expanded public-page English localization for international-student-first UX.
- 2026-02-23: Added live subtitle transform fallback signaling design (structured transform status, GPT-5 reasoning-effort control, and frontend fallback visibility).
- 2026-02-23: Added subtitle transform response compatibility guard in frontend to absorb missing/invalid `status` and prevent silent non-Japanese-view failures.
- 2026-02-23: Runtime operation switched subtitle transform Azure deployment to `gpt-4.1-nano` (`api-version=2025-01-01-preview`) to mitigate persistent fallback behavior.
- 2026-02-23: Executed live Azure deployment for API/frontend using Container Apps + Static Website, and added env-driven CORS support (`CORS_ALLOWED_ORIGINS`) for hosted frontend access.
- 2026-02-23: Migrated frontend public endpoint to Azure Static Web Apps (`proud-sand-00bb37700.1.azurestaticapps.net`) with local CLI deploy and SPA fallback config.
- 2026-02-23: Hardened API secret flow by switching Container Apps `azure-openai-api-key` to Key Vault reference (`identityref:system`) and assigning `Key Vault Secrets User` to managed identity.
- 2026-02-23: Hardened API CORS from wildcard to explicit origin allowlist (`SWA + Storage static website`) via `CORS_ALLOWED_ORIGINS`.
- 2026-02-23: Added PptxGenJS A0 poster generation implementation plan with task breakdown, dependencies, and risk mitigation.
- 2026-02-23: Added PptxGenJS A0 poster generation architecture (module boundaries, JSON schema approach, reusable component contracts, and layered configuration strategy).
- 2026-02-23: Added A0 technical poster layout decision for SIT Copilot (grid, hierarchy, section flow, visual/diagram strategy, and color/typography direction).
- 2026-02-22: Added WandB Weave observer architecture for FastAPI with Protocol/Noop patterns, async isolation, local/cloud support, and TDD-first rollout.
- 2026-02-22: Added Weave async risk matrix (likelihood/impact + concrete mitigations) for performance, memory, isolation, Azure deployment, testing, and privacy.

---

## Azure Deployment Execution Snapshot (2026-02-23)

### Decision Summary

- Deployed FastAPI backend as an externally accessible Azure Container App using image build/push via Azure Container Registry.
- Added runtime-configurable CORS origin support via `CORS_ALLOWED_ORIGINS` (default keeps local dev origins; deployment used `*` for immediate hosted access).
- Deployed frontend build artifacts to Azure Storage Static Website for same-day publishability without waiting for GitHub-connected SWA pipeline wiring.
- Set backend runtime `WEAVE_ENABLED=false` for deployment stability and lower external dependency risk in current demo environment.
- Passed Azure OpenAI key to Container Apps as app secret (`azure-openai-api-key`) and referenced it from env var mapping.

### Provisioned/Used Resources

- Resource Group: `rg-sitcopilot-dev-02210594`
- Container Registry: `acrsitc02210594`
- Container Apps Environment: `cae-sitc-02210594`
- API Container App: `ca-sitc-api-02210594`
- Frontend Static Website: `stsitc02210594` (`$web` container)

### Runtime Endpoints

- API: `https://ca-sitc-api-02210594.nicebeach-313ed1de.japaneast.azurecontainerapps.io`
- Frontend: `https://stsitc02210594.z11.web.core.windows.net/`

### Rationale

- `docs/SPEC.md` target architecture remains Azure-native, but immediate deployment priority was to publish both API and UI with minimal operational friction.
- Container Apps provides managed HTTPS ingress and revision rollout suited for FastAPI runtime.
- Static Website hosting enabled fast frontend publish from local build output while preserving a later migration path to Azure Static Web Apps.

### Compatibility Rules

- Backend image build uses repo root `Dockerfile`; runtime entrypoint must remain `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- Frontend production build must inject `VITE_API_BASE_URL` pointing to deployed API FQDN.
- For production hardening, replace wildcard CORS and app-secret injection with explicit frontend origin allowlist and Key Vault reference-based secret resolution.

---

## Azure Deployment Hardening Update (2026-02-23)

### Decision Summary

- Frontend primary public endpoint is now Azure Static Web Apps:
  `https://proud-sand-00bb37700.1.azurestaticapps.net/`
- API CORS is constrained to explicit trusted origins:
  - `https://proud-sand-00bb37700.1.azurestaticapps.net`
  - `https://stsitc02210594.z11.web.core.windows.net`
- Container Apps now resolves `AZURE_OPENAI_API_KEY` through Key Vault reference secret with system-assigned managed identity, not raw secret value injection.

### Implementation Notes

- Added `frontend/public/staticwebapp.config.json` with `navigationFallback` rewrite to `/index.html` for SPA deep links.
- Created SWA resource: `swa-sitc-02210594` (`Free`, `eastasia`), deployed using deployment token and SWA CLI.
- Assigned system identity to `ca-sitc-api-02210594`, granted `Key Vault Secrets User` on `kvsitc02210594`, then updated:
  - `azure-openai-api-key=keyvaultref:<secret-uri>,identityref:system`
- Updated API env:
  - `CORS_ALLOWED_ORIGINS` to SWA + Storage origins
  - `AZURE_OPENAI_API_KEY=secretref:azure-openai-api-key`

### Validation Results

- `GET /api/v4/health` from API endpoint returns `200`.
- CORS preflight from SWA origin with expected headers (`X-Lecture-Token`, `X-User-Id`) returns `200` and includes `access-control-allow-origin`.
- SWA deep link (`/lectures`) returns `200` via SPA fallback.

---

## GitHub Actions Main Push Auto Deployment (2026-02-23)

### Decision Summary

- Added `.github/workflows/deploy-main.yml` to trigger production deployment on every push to `main`.
- Added path-based deployment split:
  - backend targets: `app/**`, `pyproject.toml`, `uv.lock`, `Dockerfile`
  - frontend target: `frontend/**`
- Enforced backend quality gate before deploy: `uv run pytest`.
- Enforced frontend quality gate before deploy: `npm run build`.
- Backend deploy pipeline uses Azure OIDC login + ACR remote build + Container Apps image update.
- Frontend deploy pipeline uploads prebuilt `frontend/dist` artifact to Azure Static Web Apps with deployment token.
- Deployment order is fixed to `API -> frontend` when both backend and frontend changes are present.

### Compatibility Rules

- Required GitHub repository variables:
  - `AZURE_CLIENT_ID`
  - `AZURE_TENANT_ID`
  - `AZURE_SUBSCRIPTION_ID`
  - `PROD_API_BASE_URL`
- Required GitHub repository secret:
  - `AZURE_STATIC_WEB_APPS_API_TOKEN`
- Production resources remain fixed:
  - `acrsitc02210594`
  - `ca-sitc-api-02210594`
  - `rg-sitcopilot-dev-02210594`
  - `swa-sitc-02210594`
- `frontend` build and `api` smoke test both read `PROD_API_BASE_URL`; this value must point to the active production API endpoint.

### Changelog

- 2026-02-23: Added main-branch push auto deployment workflow (OIDC for API deploy + SWA deployment token), with path-based conditional execution and ordered `API -> frontend` rollout.

---

## Poster Creation Implementation Plan (2026-02-23)

### Project: SIT Copilot A0 Poster for AI Innovators Cup

**Goal**: Create presentation-quality A0 poster using PptxGenJS showcasing SIT Copilot for competition.

### Implementation Tasks

| Phase | Task | Description | Dependencies | Effort |
|-------|------|-------------|--------------|--------|
| **1. Setup** | 1.1 Initialize TypeScript project | `poster-gen/` dir, package.json, tsconfig, pnpm | None | 30m |
| | 1.2 Install PptxGenJS | Add `pptxgenjs` and type definitions | 1.1 | 10m |
| | 1.3 Configure build | Vite or tsx for dev, npm scripts | 1.1 | 20m |
| **2. Foundation** | 2.1 Implement layout module | A0 constants, mm→inch, grid system (12-col) | 1.2 | 1h |
| | 2.2 Implement theme tokens | Color palette, typography scale, spacing | None | 45m |
| | 2.3 Create schema validator | JSON schema + Zod runtime validation | 1.2 | 45m |
| **3. Components** | 3.1 Build primitive renderers | text-block, shape-block, image-block wrappers | 2.1, 2.2 | 1.5h |
| | 3.2 Build section component | Container with title, background, grid area | 3.1 | 1h |
| | 3.3 Build header component | Title, subtitle, authors, logo, QR code | 3.1 | 1h |
| | 3.4 Build metric-card component | KPI display with accent styling | 3.1 | 45m |
| | 3.5 Build figure component | Image with caption, fit modes | 3.1 | 45m |
| **4. Content** | 4.1 Create poster JSON schema | Define content structure for SIT Copilot | 2.3 | 1h |
| | 4.2 Write poster content JSON | Fill in background, objectives, AI usage, results | 4.1 | 2h |
| | 4.3 Create architecture diagram | SVG/diagram for system architecture | None | 2h |
| **5. Integration** | 5.1 Build poster renderer | Orchestrate all components, layout engine | 3.x, 4.2 | 1.5h |
| | 5.2 Add CLI entry point | Config path, output path, validation | 5.1 | 45m |
| | 5.3 Create preview script | Generate PPTX and open for review | 5.2 | 30m |
| **6. Polish** | 6.1 Visual refinement | Adjust spacing, alignment, contrast | 5.3 | 1h |
| | 6.2 Print preparation | Verify DPI, bleed, export to PDF | 6.1 | 30m |
| | 6.3 Final review | Competition requirements checklist | 6.2 | 30m |

**Total Estimated Effort**: ~16-18 hours

### Task Dependencies

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundation)
    ↓
Phase 3 (Components) ← Phase 4 (Content, can be parallel)
    ↓           ↓
Phase 5 (Integration)
    ↓
Phase 6 (Polish)
```

### Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| PptxGenJS API limitations | Medium | Medium | Prototype early with text/shapes; verify A0 support |
| Font rendering issues | Medium | High | Use system fonts; test Japanese text early |
| Diagram creation bottleneck | High | Medium | Use simple flowchart libraries or manual SVG |
| Content doesn't fit A0 | Low | High | Grid system prevents overflow; early preview |
| Print quality issues | Low | High | Verify DPI >300; use vector graphics |
| Competition req changes | Low | Medium | Keep content in JSON for easy updates |

### File Structure (Final)

```
poster-gen/
├── package.json
├── tsconfig.json
├── src/
│   ├── app/
│   │   ├── build-poster.ts       # Main entry
│   │   └── cli.ts                # CLI interface
│   ├── domain/
│   │   ├── poster-schema.ts      # Type definitions
│   │   └── validator.ts          # Zod validation
│   ├── layout/
│   │   ├── a0.ts                 # A0 dimensions, grid
│   │   └── placement.ts          # Auto-layout logic
│   ├── theme/
│   │   ├── tokens.ts             # Design tokens
│   │   └── presets/
│   │       └── tech-blue.ts      # SIT Copilot theme
│   ├── components/
│   │   ├── header.ts
│   │   ├── section.ts
│   │   ├── text-block.ts
│   │   ├── figure-block.ts
│   │   ├── metric-card.ts
│   │   ├── footer.ts
│   │   └── registry.ts           # Component registry
│   ├── renderer/
│   │   ├── pptx-factory.ts       # PptxGenJS initialization
│   │   ├── master.ts             # Slide master
│   │   ├── primitives-text.ts
│   │   ├── primitives-shape.ts
│   │   ├── primitives-image.ts
│   │   └── poster-renderer.ts
│   ├── config/
│   │   ├── default.json
│   │   └── loader.ts
│   └── infra/
│       ├── asset-loader.ts
│       └── logger.ts
├── posters/
│   └── sit-2026-a0.json          # Poster content
├── assets/
│   ├── images/
│   │   ├── logo.png
│   │   └── architecture-diagram.svg
│   └── icons/
└── dist/
    └── sit-copilot-a0.pptx        # Output
```

### Content Schema Example

```typescript
interface PosterContent {
  version: string;
  posterId: string;
  page: {
    size: "A0";
    orientation: "portrait";
    grid: { columns: 12; gutterMm: 6; rowMm: 8 };
  };
  theme: {
    preset: "tech-blue";
    fontFamilyJa: "Noto Sans JP";
  };
  header: {
    title: string;
    subtitle: string;
    authors: Array<{ name: string; affiliation: string }>;
    logo?: string;
    qrCode?: string;
  };
  sections: Array<{
    id: string;
    title: string;
    area: { colStart: number; colSpan: number; rowStart: number; rowSpan: number };
    blocks: Array<TextBlock | ImageBlock | ShapeBlock | MetricBlock>;
  }>;
}
```

### Success Criteria

- [ ] Poster generates as A0 PPTX file
- [ ] All sections visible and properly aligned
- [ ] Japanese text renders correctly
- [ ] Architecture diagram is clear and readable
- [ ] QR code for demo video is included
- [ ] Color contrast meets accessibility standards
- [ ] Content covers all competition requirements
- [ ] File size is reasonable for printing (<50MB)

---

## Live Mini QA Migration (2026-02-23)

### Decision Summary

- Removed frontend review UI pages (`/lectures/:id/review`, `/lectures/:id/qa`, `/lecture/:session_id/qa`) and redirected legacy paths to `/lectures`.
- Migrated lecture grounded QA execution to live right rail mini-question flow (`AssistPanel`) so users can ask and receive cited answers during live session.
- Kept backend lecture QA APIs (`/api/v4/lecture/qa/index/build`, `/ask`, `/followup`) unchanged and reused them from live UI.
- Adopted follow-up policy: first question uses `ask`, second and later questions use `followup`.
- Adopted index refresh policy for live QA: rebuild lecture QA index at most once per 30 seconds with `rebuild=true` to balance freshness and load.
- Added sequential subtitle IDs (`S-001`, `S-002`, ...) to finalized transcript lines, and prefixed mini QA audio citation labels with the resolved subtitle ID.
- Removed ended-session navigation target from lecture list; ended sessions remain visible but non-navigable.

### Rationale

- Eliminates duplicated QA surfaces and concentrates user flow in live screen where ASR evidence is generated.
- Preserves proven backend contract and test surface while minimizing API migration risk.
- 30-second rebuild cadence avoids stale ASR retrieval while preventing per-question rebuild overload.
- Subtitle ID prefixes improve traceability by making answer evidence point back to exact transcript lines.

### Compatibility Rules

- Existing direct links to removed review routes must not break: they are redirected to `/lectures`.
- Procedure QA remains unchanged and continues to reuse shared QA block/store utilities.
- Naming cleanup of `review*` frontend modules is explicitly deferred; only feature migration is in scope for this change.
- QA API contract remains unchanged; subtitle ID decoration is a frontend-only mapping using existing `citationId` chunk references.
- Inline answer references that point to audio timestamps are normalized from `[timestamp]` to `S-xxx` in the live mini QA renderer.

### Changelog

- 2026-02-23: Migrated lecture grounded QA from review pages into live mini-question panel; removed review UI routes/pages and added legacy route redirects.
- 2026-02-23: Added finalized-transcript sequential subtitle IDs and mini QA citation label prefixing (`S-xxx`) for evidence traceability.
- 2026-02-23: Replaced inline audio timestamp references (`[hh:mm:ss]` style labels) in mini QA answer text with subtitle IDs (`S-xxx`) for consistency with citation chips.

---

## Lecture Session Delete Legacy Compatibility (2026-02-23)

### Decision Summary

- Updated lecture session delete flow to treat legacy `ended` status as deletable finalized state.
- Kept auto-finalize behavior unchanged for active-style statuses (`active`, `live`).

### Rationale

- Some legacy rows still carry `ended`; rejecting them with `409` caused delete-button failures in the lecture list UI.
- Allowing deletion for `ended` keeps backward compatibility without changing current lifecycle (`active` -> `finalized`).

### Compatibility Rules

- Delete endpoint continues to reject truly invalid states (e.g., `error`), preserving safety checks.
- This change is backward-compatible and does not modify API schema or response fields.

### Changelog

- 2026-02-23: Added backend delete compatibility for legacy `ended` lecture session rows to prevent `409` failures from UI delete actions.

---

## Lecture Session Delete QA-Turn Cleanup (2026-02-24)

### Decision Summary

- Added explicit `qa_turns` cleanup in lecture session delete flow (`SqlAlchemyLectureFinalizeService.delete_session`).
- Kept response schema and endpoint contract unchanged (`DELETE /api/v4/lecture/session/{id}` with `auto_finalized` flag).

### Rationale

- Some environments can carry lecture-linked QA history rows while deleting sessions.
- Explicitly removing `qa_turns` by `session_id` makes deletion robust across schema variants and prevents leftover orphan QA history for deleted sessions.

### Compatibility Rules

- Procedure QA rows (`feature=procedure_qa`, `session_id=NULL`) are unaffected.
- Lecture delete behavior remains backward-compatible for `active`/`live`/`finalized`/`ended` statuses.
- API response payload remains unchanged.

### Changelog

- 2026-02-24: Added explicit `qa_turns` deletion in lecture session delete flow and extended tests to verify QA-turn cleanup.

---

## Production Live-Only UI Scope Reduction (2026-02-23)

### Decision Summary

- Narrowed frontend product scope to real-time lecture support only.
- Removed non-live entry points from landing: pre-course support (F0), procedure QA, demo screenshot, and non-live feature bullets.
- Locked down `/procedure` and `/readiness-check` routes by redirecting both to `/lectures`.
- Removed lecture-list readiness score surface and removed readiness pre-check call from session start flow.
- Removed live left sidebar (`SourcePanel`) and camera toggle from live top bar to hide OCR/material panel functionality in production UI.
- Removed predefined quick-question chips from `AssistPanel`; kept free-text mini QA input.
- Replaced user-facing "demo" wording across frontend UI/error messages with production-neutral wording.

### Rationale

- Production launch requires a single clear use case and minimal operator confusion during live classes.
- Hiding non-target functionality at route and UI levels reduces accidental usage and expectation mismatch.
- Keeping backend/internal identifiers unchanged lowers migration risk while allowing immediate UI hardening.

### Compatibility Rules

- Internal API/service identifiers (e.g., `demoApi`, `DEMO_USER_ID`) remain unchanged in this phase.
- Route behavior changes are intentional: direct access to `/procedure` and `/readiness-check` is no longer available.
- Existing live transcript and mini QA backend flows stay intact; this change only narrows visible UI scope.

### Changelog

- 2026-02-23: Restricted production UI scope to real-time lecture support and removed non-live landing entry points.
- 2026-02-23: Redirected `/procedure` and `/readiness-check` to `/lectures` and removed live SourcePanel/camera toggle from UI.
- 2026-02-23: Removed readiness score UI/pre-check call and replaced user-facing "demo" wording with production-neutral text.

---

## Lecture Session Panel Recovery Rules (2026-02-23)

### Decision Summary

- Added resilient recovery for lecture-list session actions (`finalize`, `delete`) against stale local sessions and state drift.
- Normalized persisted session statuses in localStorage:
  - `active`/`live` -> `live`
  - `finalized`/`ended` -> `ended`
- On finalize:
  - `409` keeps idempotent behavior and marks local card as ended.
  - `404` removes stale local card and notifies user.
- On delete:
  - `404` removes stale local card.
  - `409` triggers one recovery attempt (`finalize` -> `delete` retry), then applies standard error handling.

### Rationale

- Local session cards can become stale after backend restarts, user-id changes, or legacy status data.
- Without recovery, users can get stuck with non-operable cards and repeated failure to close/delete sessions.
- The recovery path keeps UI operable without changing backend APIs.

### Compatibility Rules

- Backend API contracts remain unchanged (`/session/start`, `/session/finalize`, `DELETE /session/{id}`).
- Internal naming (`demoApi`, storage key) remains unchanged in this phase.
- Recovery behavior is local-UI only and does not alter session ownership checks on server side.

### Changelog

- 2026-02-23: Added lecture-list finalize/delete recovery for stale sessions and legacy persisted status values.

---

## Auto Session Title from Lecture Content (2026-02-23)

### Decision Summary

- Added automatic session title generation on lecture finalize in `LecturesPage`.
- Auto-title runs only when the current title is still the placeholder pattern (`講義セッション ...`).
- Title source is `GET /api/v4/lecture/summary/latest`:
  - Prefer first key term + first summary sentence.
  - Fallback to first summary sentence only.
- Generated title is normalized (whitespace/punctuation cleanup) and truncated to UI-safe length.
- If summary is unavailable (`no_data`) or API fails, current title is kept unchanged.

### Rationale

- Placeholder session names are not meaningful in production review flow.
- Finalize timing ensures enough lecture context is available to generate a useful title.
- Restricting auto-title to placeholder names avoids overwriting curated/custom titles.

### Compatibility Rules

- No backend API/schema changes required; uses existing summary endpoint.
- Storage key and session list persistence format stay compatible with prior data.
- Auto-title is best-effort and non-blocking; finalize behavior remains unchanged if title generation fails.

### Changelog

- 2026-02-23: Added finalize-time automatic session title generation from lecture summary/key terms for placeholder-titled sessions.

---

## Lecture QA Answer Language Routing (2026-02-24)

### Decision Summary

- Improved `AzureOpenAILectureAnswererService._build_prompt()` to include explicit output language instruction.
- Added language routing logic for lecture QA answers:
  - `lang_mode="en"` always outputs English.
  - English questions (Latin letters present, Japanese characters absent) also output English.
  - `lang_mode="easy-ja"` outputs やさしい日本語 when question is not English.
  - Otherwise outputs Japanese.
- Added stricter English-path controls in answer generation:
  - English question path now uses English-first prompt template and English-only system instruction.
  - No-source/action-next/local fallback text is localized to English for English questions.
- Added fallback-safe language routing in `SqlAlchemyLectureQAService`:
  - Effective answer lang_mode is upgraded to `en` when the user question is English.
  - Local grounded fallback responses from QA service are also emitted in English for English questions.
- Added follow-up rewrite language preservation:
  - `LectureFollowupService` uses an English rewrite prompt for English questions and explicitly preserves question language.
- Updated frontend mini QA request language source:
  - `requestReviewQaAnswer` now accepts `easy-ja`.
  - Live page sends current session `selectedLanguage` instead of stale/optional settings language.
- Added unit tests to lock language-instruction behavior in prompt generation.

### Rationale

- Previous prompt text was Japanese-only, which caused Japanese answers even when users asked in English.
- Explicit language routing in prompt keeps current QA architecture unchanged while fixing user-facing response language behavior.

### Compatibility Rules

- Retrieval/verification/persistence flow remains unchanged; only prompt construction logic is updated.
- Existing API contracts and schema are unchanged.
- English detection is intentionally conservative (mixed Japanese+English questions default to `lang_mode` behavior).

### Changelog

- 2026-02-24: Added prompt-level response language routing for lecture QA so English questions are answered in English.
- 2026-02-24: Strengthened English-path QA controls across answer/fallback/followup rewrite/frontend lang-mode wiring to prevent Japanese responses to English questions.

---

## Local Dev Server Script (2026-02-24)

### Decision Summary

- Added unified local runtime script: `scripts/dev-server.sh`.
- Script supports `start|stop|restart|status|logs` for `backend|frontend|all`.
- Runtime artifacts are centralized under `.runtime/`:
  - PID files: `backend.pid`, `frontend.pid`
  - Logs: `backend.log`, `frontend.log`
- Backend startup via script defaults to `WEAVE_ENABLED=false` for stable local startup, while allowing override through environment variable.
- Updated process launch mode to improve detach stability:
  - prefer `setsid` for backend/frontend detached startup.
  - frontend starts `node_modules/.bin/vite` directly (no `npm run` wrapper).
  - frontend uses `--strictPort` to fail-fast on port mismatch instead of auto-port hopping.

### Rationale

- Repeated manual startup/restart commands increased operational friction during verification loops.
- Single command entrypoint reduces human error and speeds up local QA iteration.
- Disabling Weave by default in script avoids startup hangs in environments without reliable Weave connectivity.

### Compatibility Rules

- Existing manual startup commands remain valid and documented in README as fallback.
- Script is intended for local development; production/deployment flows are unchanged.

### Changelog

- 2026-02-24: Added `scripts/dev-server.sh` and documented quick startup/restart workflow in README.
- 2026-02-24: Hardened `scripts/dev-server.sh` detached launch (`setsid`, direct `vite`, strict port) to prevent intermittent local `ERR_CONNECTION_REFUSED` due process drop.

---

## Live Session Lifecycle Stabilization (2026-02-24)

### Decision Summary

- Fixed live-page microphone/speech lifecycle to auto-start per `sessionId` instead of one-time-per-component:
  - replaced boolean `autoStartAttemptedRef` with session-scoped tracking.
  - added explicit session-switch cleanup (`stopRecording`, `resetLiveData`, `setSessionId(null)`).
- Isolated stream-subscription cleanup from microphone teardown:
  - stream reconnect/re-subscribe cleanup now only unsubscribes/disconnects stream transport.
  - microphone/live-state teardown is handled on session switch and component unmount only.
- Hardened lecture-list local persistence scope:
  - moved session storage key to scoped format (`v2` + API base + demo user id).
  - deduplicates persisted entries by `session_id` when loading.
- Updated finalize error policy in lecture list:
  - `409` is no longer treated as implicit success/ended-state.
  - surface `409` as warning/failure to avoid creating phantom local state drift.

### Rationale

- Intermittent "no response after entering a new session" was caused by lifecycle races:
  - recording could be stopped by stream-effect cleanup during re-subscription,
  - while auto-start guard prevented re-start in the same component lifecycle.
- Session finalize/delete confusion was amplified by global localStorage scope and optimistic `409` handling.
- Session-scoped auto-start + scoped storage + strict `409` handling keeps UI state closer to server truth.

### Compatibility Rules

- Backend lecture API contracts remain unchanged.
- Existing persisted lecture-list entries under legacy key are intentionally not auto-migrated.
- New storage scope is per `(API base, demo user id)` to avoid cross-environment/session contamination.

### Changelog

- 2026-02-24: Stabilized live session audio lifecycle and prevented stream cleanup from stopping microphone unexpectedly.
- 2026-02-24: Scoped lecture-list storage key (v2) and removed optimistic finalize-on-409 local state mutation.

---

## Poster QA Screenshot Additive Variant (2026-02-26)

### Decision Summary

- Created an additive poster variant that keeps the existing live screenshot and adds QA screenshot evidence:
  - New source file: `poster-gen/poster-preview-qa-added.html`
  - New output image: `poster-gen/poster-preview-output-qa-added.png`
- Section 3 screenshot area was changed from single-image to dual-pane:
  - left: live lecture screen (`live-screen.png`)
  - right: QA screen (`qa-screen.png`)
- Added short pane titles and updated caption/legend so reviewers can read QA evidence behavior before scanning QR.

### Rationale

- The previous layout had no dedicated QA screenshot, making source-only QA behavior under-explained.
- Additive two-pane layout preserves existing narrative while making citation behavior (`source_id`) visually explicit.
- Aspect-ratio constraints were set per pane to keep A0 composition stable without overflowing page height.

### Compatibility Rules

- Do not replace the current poster by default; keep this as a comparison variant.
- Preserve factual metrics and avoid adding new claims or URLs in printed text.
- Keep A0 export size at `3400 x 4804` for preview outputs.

### Changelog

- 2026-02-26: Added QA screenshot additive poster variant with dual-pane screenshot layout and A0-safe export.
- 2026-02-26: Added inset-style QA screenshot variant (`poster-preview-qa-inset.html`) where QA evidence is shown as a small overlay card on the live screenshot.
- 2026-02-26: Rebalanced section heights by returning QA screenshot pair to section 4 and compressing section 5 notes into compact horizontal chips.

---

## Poster A0 No-Margin PDF Export (2026-02-26)

### Decision Summary

- For no-margin A0 delivery, export flow was switched to:
  1) render final poster HTML to PNG,
  2) trim outer screen-background border,
  3) place trimmed image to full A0 page and export single-page PDF.
- Output file remains `poster-gen/poster-preview-a0.pdf`.

### Rationale

- Direct HTML `playwright pdf` path can retain screen-frame artifacts or style differences from WebUI.
- Image-first export preserves on-screen appearance while guaranteeing zero page margin and single-page A0.

### Compatibility Rules

- Always verify with `pdfinfo`:
  - `Pages: 1`
  - `Page size: A0`
- Re-run trim step when body/frame styling changes.

### Changelog

- 2026-02-26: Adopted no-margin A0 PDF export via trimmed PNG embedding.

---

## Poster A0 Export Skillization (2026-02-26)

### Decision Summary

- Packaged the no-margin A0 poster export method as a Codex skill:
  - Skill path: `.codex/skills/poster-a0-no-margin-export`
  - Workflow: `HTML screenshot -> border trim -> full-page A0 PDF`
- Added reusable scripts:
  - `.codex/skills/poster-a0-no-margin-export/scripts/export_a0_no_margin.sh`
  - `.codex/skills/poster-a0-no-margin-export/scripts/trim_uniform_border.py`
- Default output contract targets `poster-gen/SIT_Copilot_Poster.pdf` with PDF title `SIT_Copilot_Poster`.

### Rationale

- Poster delivery repeats the same export operation across many edit loops.
- Converting the flow to a skill reduces manual command drift and keeps PDF output consistent.

### Compatibility Rules

- Use `pdfinfo` gate after export:
  - `Pages: 1`
  - `Page size: A0`
- Keep source poster content unchanged during export; this skill is render-only.
- Ignore transient poster iteration artifacts in git:
  - `poster-gen/poster_v*.png`
  - `poster-gen/poster-preview-a0-page*.png`

### Changelog

- 2026-02-26: Added `poster-a0-no-margin-export` skill with script-driven no-margin A0 PDF export.
- 2026-02-26: Added `.gitignore` patterns for poster intermediate iteration images.
