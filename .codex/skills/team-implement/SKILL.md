---
name: team-implement
description: Execute implementation from an approved /startproject plan using Codex only, with optional Gemini support for analysis. No Claude Agent Teams dependency.
---

# Team Implement (Codex Native)

Implement approved plans without Claude Agent Teams. Use workstream ownership and staged integration.

## Prerequisites

- `/startproject` plan approved by the user
- `.claude/docs/research/{feature}-plan.md` exists
- `.claude/docs/DESIGN.md` is up to date

## Workflow

1. Build execution lanes
   - Derive 2-4 workstreams from the plan (for example: data, service, api, tests).
   - Assign strict file ownership per workstream to avoid conflicts.
   - Record ownership in the response before editing using this template:

     | Lane | Goal | Owned Files | Depends On | Lane Checks |
     |------|------|-------------|------------|-------------|
     | data | ... | `path/a.py`, `path/b.py` | none | `ruff/ty/pytest <scope>` |
     | service | ... | ... | data | ... |
     | api | ... | ... | service | ... |
     | tests | ... | ... | api | ... |

   - Rules:
     - Only the owning lane edits listed files.
     - Cross-lane interface changes must be announced and immediately synchronized.
     - Do not begin lane implementation until ownership table is published.

2. Implement by workstream
   - Execute each lane end-to-end on its owned files.
   - Keep interfaces stable; when interface changes are required, update dependent lanes immediately.
   - Prefer small, verifiable commits in logical chunks.

3. Validate per lane
   - Run focused checks after each lane:
     - `uv run ruff check <scope>`
     - `uv run ty check <scope>`
     - `uv run pytest <scope>`
   - Declare lane complete only when all conditions are met:
     - Owned-file implementation done.
     - Lane checks pass in that lane scope.
     - Interface changes (if any) documented and synchronized to dependent lanes.
     - No edits outside owned files, or deviation explicitly approved and recorded.

4. Integrate and verify globally
   - Run merge gate checks in this order:
     - `uv run ruff check .`
     - `uv run ruff format --check .`
     - `uv run ty check app/`
     - `uv run pytest -v`
   - If global checks fail due pre-existing unrelated issues, record:
     - failing command
     - failing file scope
     - reason it is outside current lanes
     - lane-scope checks proving new changes are clean

5. Report implementation status
   - Provide completed tasks, changed files, quality gate results, and residual risks.
   - Include lane-by-lane completion table and merge gate status.
   - If complete, recommend `/team-review`.

## Lane Completion Template

Use this table for final lane reporting:

| Lane | Owned Files | Lane Scope Checks | Interface Sync | Status |
|------|-------------|-------------------|----------------|--------|
| data | `...` | `ruff/ty/pytest` pass/fail | none/updated | done/in progress |
| service | `...` | ... | ... | ... |
| api | `...` | ... | ... | ... |
| tests | `...` | ... | ... | ... |

## Merge Gate Template

Use this template before sign-off:

| Gate | Result | Evidence |
|------|--------|----------|
| `ruff check .` | pass/fail | command + key output |
| `ruff format --check .` | pass/fail | command + key output |
| `ty check app/` | pass/fail | command + key output |
| `pytest -v` | pass/fail | command + key output |

## Command Contract

- `/team-implement`
