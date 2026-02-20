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
   - Record ownership in the response before editing.

2. Implement by workstream
   - Execute each lane end-to-end on its owned files.
   - Keep interfaces stable; when interface changes are required, update dependent lanes immediately.
   - Prefer small, verifiable commits in logical chunks.

3. Validate per lane
   - Run focused checks after each lane:
     - `uv run ruff check <scope>`
     - `uv run ty check <scope>`
     - `uv run pytest <scope>`

4. Integrate and verify globally
   - Run full project checks:
     - `uv run ruff check .`
     - `uv run ruff format --check .`
     - `uv run ty check app/`
     - `uv run pytest -v`

5. Report implementation status
   - Provide completed tasks, changed files, quality gate results, and residual risks.
   - If complete, recommend `/team-review`.

## Command Contract

- `/team-implement`
