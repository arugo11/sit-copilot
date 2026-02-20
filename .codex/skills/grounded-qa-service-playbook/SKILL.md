---
name: grounded-qa-service-playbook
description: Build and harden evidence-first QA/RAG services with deterministic no-source fallback, verification, and persistence. Use when users ask for grounded QA, transcript-native QA, RAG endpoint design, citation verification, or say "根拠必須", "no-source fallback", "hallucination対策".
---

# Grounded Qa Service Playbook

Implement grounded QA as a strict staged pipeline and keep hallucination risk observable.

## Workflow

1. Freeze grounded response contract
   - Define response fields:
     - `answer`
     - `confidence`
     - `sources` / citations
     - `fallback`
     - optional verification summary
   - Define deterministic no-source behavior (`sources == []` -> low confidence fallback).

2. Separate service interfaces
   - Create Protocol boundaries for:
     - retrieval
     - answer generation
     - verification
     - orchestration
   - Keep API route layer thin and DI-based.

3. Build retrieval path first
   - Implement index build and retrieval.
   - Ensure index lifecycle is valid across requests (no per-request reset bug).

4. Wire answer + verification
   - Connect model settings from config/env (do not hardcode empty credentials).
   - Enforce evidence-only prompt policy.
   - Parse verifier output conservatively (fail closed on parse errors).

5. Persist QA turns
   - Save question, answer, confidence, citations, latency, and feature tags.
   - Keep storage format stable for later audit and analytics.

6. Add mandatory tests
   - API:
     - auth required
     - index build -> ask E2E
     - no-index/no-source fallback
   - Service:
     - verification fail/repair path
     - context expansion behavior

7. Run hardening review
   - Execute security, quality, and tests review pass.
   - Classify and fix Critical/High before sign-off.

8. Apply release acceptance gate
   - Contract acceptance:
     - `sources == []` always returns deterministic low-confidence fallback.
     - If citations exist, every citation must map to retrieved context IDs.
   - Verification acceptance:
     - Verifier parse errors are fail-closed (no unverifiable confident answer).
     - Confidence downgrade rules are explicit and tested.
   - Persistence acceptance:
     - Stored fields include question/answer/confidence/citations/latency/tags.
     - Failed/no-source outcomes are stored with reason codes for audit.
   - Test acceptance:
     - E2E happy path (index -> ask) passes.
     - no-source path passes.
     - verifier-fail path passes.
     - auth and input validation paths pass.
   - Security acceptance:
     - No secrets hardcoded.
     - Error responses do not leak internal connection/model details.

## Output Contract

- Must provide:
  - pipeline diagram or ordered steps
  - fallback policy statement
  - verification policy statement
  - test matrix (happy/error/ownership/security)
  - acceptance gate result (pass/fail per gate)

## Acceptance Matrix Template

Use this matrix for implementation/review handoff:

| Gate | Check | Result | Evidence |
|------|-------|--------|----------|
| Fallback determinism | `sources == []` => fixed low-confidence fallback | pass/fail | test name + output |
| Citation integrity | citations map to retrieved context IDs | pass/fail | service/API test |
| Verifier fail-closed | parse/verification failure blocks confident answer | pass/fail | unit test |
| Persistence auditability | all required fields + reason code stored | pass/fail | schema/store test |
| Security baseline | no hardcoded secrets / safe error messages | pass/fail | code review notes |

## Command Contract

- `/grounded-qa-service-playbook <feature>`
