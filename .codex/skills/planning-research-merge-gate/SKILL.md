---
name: planning-research-merge-gate
description: Run planning and research in parallel and enforce a merge gate before implementation. Use when users ask for architecture with evidence, say "設計と調査を並行で", "根拠付きで設計を固めて", "merge gate", or request a pre-implementation design freeze with risks and acceptance criteria.
---

# Planning Research Merge Gate

Plan with two explicit tracks and merge only after evidence checks pass.

## Workflow

1. Define the planning unit
   - Capture `{feature}`, goals, in-scope, out-of-scope, constraints, and success criteria.

2. Run architecture and research tracks
   - Architecture track:
     - Analyze local structure with `rg --files`, `rg -n`, and focused file reads.
     - Draft modules, boundaries, data flow, and risk table.
   - Research track:
     - Gather unresolved library/runtime constraints.
     - Record version requirements, known pitfalls, and operational limits.

3. Persist both tracks separately
   - Save to:
     - `.claude/docs/research/{feature}-codebase.md`
     - `.claude/docs/research/{feature}.md`

4. Enforce merge gate
   - Produce `.claude/docs/research/{feature}-plan.md` only if all checks pass:
     - scope is unambiguous
     - architecture and research do not conflict
     - acceptance criteria are testable
     - major risks have mitigation
   - If any check fails, stop and report blockers first.

5. Persist design decisions
   - Update `.claude/docs/DESIGN.md` with key decisions, rationale, and open questions.

6. Ask for explicit go/no-go
   - Request user approval before implementation.

## Output Contract

- Required files:
  - `.claude/docs/research/{feature}-codebase.md`
  - `.claude/docs/research/{feature}.md`
  - `.claude/docs/research/{feature}-plan.md`
  - `.claude/docs/DESIGN.md` update
- Required response:
  - merge gate result (`pass` or `blocked`)
  - top risks
  - approval question

## Command Contract

- `/planning-research-merge-gate <feature>`
