---
name: owner-lane-team-implement
description: Implement an approved plan using strict ownership lanes to reduce conflicts and regressions. Use when users ask for "担当を分けて実装", "競合を避けて並列実装", "lane-based implementation", or want staged integration with per-lane quality gates.
---

# Owner Lane Team Implement

Execute implementation with file-ownership lanes and stage gates.

## Prerequisites

- Approved plan exists (`.claude/docs/research/{feature}-plan.md`)
- Scope freeze is accepted by the user

## Workflow

1. Build lane table
   - Define 2-4 lanes (for example: `data`, `service`, `api`, `tests`).
   - Assign each lane:
     - owned files
     - interface dependencies
     - done criteria
   - Publish lane table before editing.

2. Implement lane by lane
   - Edit only lane-owned files.
   - If interface changes are unavoidable:
     - apply consumer updates immediately
     - note impacted lanes in status

3. Run lane-level gates
   - Execute focused checks:
     - `uv run ruff check <scope>`
     - `uv run pytest <scope>`
     - type check command configured for the project
   - Fix lane failures before next lane.

4. Integrate globally
   - Run project-wide checks:
     - `uv run ruff check .`
     - `uv run ruff format --check .`
     - project type check command
     - `uv run pytest -q`

5. Deliver structured report
   - Include:
     - lane completion matrix
     - changed files by lane
     - gate outcomes
     - residual risks and follow-ups

## Output Contract

- Lane table is mandatory.
- Global gate results are mandatory.
- Residual-risk list is mandatory.

## Command Contract

- `/owner-lane-team-implement <feature>`
