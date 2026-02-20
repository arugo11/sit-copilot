# Skill Pattern Analysis (from checkpoint 2026-02-20-193350)

## Checkpoint Stats

- Commits: 0
- Files changed: 0
- Codex consultations: 0
- Gemini researches: 0
- Agent Teams sessions: 4
- Teammate logs: 8
- Major evidence source: Agent team work logs in `.claude/logs/agent-teams/*`

## Candidate Patterns (confidence >= 0.6)

## 1) `planning-research-sync`

- Description: Architect and Researcher run in parallel, then converge into a single design decision set and implementation plan.
- Trigger phrases (JA):
  - 「設計と調査を並行で進めたい」
  - 「実装前に根拠付きで設計を固めて」
- Trigger phrases (EN):
  - "Run planning and research in parallel"
  - "Finalize design with evidence before implementation"
- Workflow:
  1. Split into `architect` and `researcher` tracks.
  2. Architect drafts architecture, API contract, and step plan.
  3. Researcher validates library/runtime pitfalls and version constraints.
  4. Merge into `DESIGN.md` + risk table + explicit TODO/open questions.
  5. Gate implementation until merge is approved.
- Confidence: 0.84
- Evidence:
  - `sprint1-settings-api-and-db` logs show Architect + Researcher roles with explicit design + validation handoff.
  - Sprint docs include merged outputs: data model, DB session pattern, and risk mitigations.
- Existing skill overlap:
  - Closest existing: `startproject`
  - Recommendation: extend `startproject` with an explicit "merge gate checklist" template.

## 2) `owner-sliced-implementation`

- Description: Implement by strict file ownership lanes (DB/models, schemas/services, API/tests) to avoid conflicts and reduce integration churn.
- Trigger phrases (JA):
  - 「担当レーンを分けて実装して」
  - 「競合しない並列実装で進めたい」
- Trigger phrases (EN):
  - "Implement with strict file ownership"
  - "Parallelize implementation without merge conflicts"
- Workflow:
  1. Define 2-4 lanes and file ownership.
  2. Each lane executes TDD end-to-end in owned files only.
  3. Run lane-level lint/type/test gates.
  4. Integrate and run global quality gates.
  5. Record outcomes and residual risks.
- Confidence: 0.79
- Evidence:
  - `sprint1-implement` and later Sprint2 execution used role split (`db-models`, `schema-service`, `api-tests`) and staged validation.
- Existing skill overlap:
  - Closest existing: `team-implement`
  - Recommendation: add a reusable "lane ownership table" output template to `team-implement`.

## 3) `evidence-first-qa-hardening`

- Description: For QA endpoints, enforce no-evidence fallback, persist turn metadata, then harden via security/quality/test review findings.
- Trigger phrases (JA):
  - 「根拠必須でQAを実装して」
  - 「レビュー指摘をすぐ反映して」
- Trigger phrases (EN):
  - "Implement evidence-required QA flow"
  - "Apply review findings immediately"
- Workflow:
  1. Implement retrieval/answer contracts with fake adapters first.
  2. Add deterministic guard (`no sources => fallback`).
  3. Persist QA turn fields needed for audit/analysis.
  4. Run multi-pass review (security/quality/tests).
  5. Patch Medium findings immediately (auth, DI, validation, tests).
- Confidence: 0.88
- Evidence:
  - Sprint2 artifacts show rootless-answer blocking, `qa_turns` persistence, and post-review hardening.
  - Added auth boundary + DI + validation + tests after review.
- Existing skill overlap:
  - Crosses `team-implement` + `team-review`
  - Recommendation: add this as a focused sub-playbook under `team-review` for grounded QA endpoints.

## 4) `checkpoint-to-pattern-mining`

- Description: After implementation/review, run checkpoint generation and convert session activity into actionable skill candidates.
- Trigger phrases (JA):
  - 「このセッションをチェックポイント化して」
  - 「再利用できる作業パターンを抽出して」
- Trigger phrases (EN):
  - "Checkpoint this session"
  - "Extract reusable skill patterns"
- Workflow:
  1. Generate checkpoint artifacts.
  2. Verify checkpoint files + session history update.
  3. Analyze `.analyze-prompt.md` for recurring multi-step patterns.
  4. Classify confidence and overlap with existing skills.
  5. Propose create/extend/defer actions.
- Confidence: 0.76
- Evidence:
  - Current workflow executed exactly with generated checkpoint + analysis prompt files.
- Existing skill overlap:
  - Closest existing: `checkpointing`
  - Recommendation: include a standard "pattern candidate report" output section in checkpointing by default.

## Suggested Next Actions

1. Extend `team-implement` with a lane-ownership template (high ROI, low risk).
2. Extend `team-review` with "evidence-first QA hardening checklist" for API endpoints.
3. Extend `startproject` with a planning-research merge gate checklist.
4. Keep `checkpointing` as-is but add optional auto-write of skill pattern report path.

