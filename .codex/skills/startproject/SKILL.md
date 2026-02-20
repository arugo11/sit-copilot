---
name: startproject
description: Start project planning in Codex without Claude dependencies. Use when the user asks for /startproject to define scope, research with Gemini, create architecture, and prepare an approved implementation plan.
---

# Start Project (Codex Native)

Plan a feature with Codex + Gemini only. Do not require Claude Agent Teams, Task tool, or subagents.

## Inputs

- Feature name: `{feature}`
- Optional context files from the user

## Outputs

- `.claude/docs/research/{feature}-codebase.md`
- `.claude/docs/research/{feature}.md`
- `.claude/docs/research/{feature}-plan.md`
- `.claude/docs/DESIGN.md` (decision updates)

## Workflow

1. Load project context
   - Read `.claude/rules/*` and `.claude/docs/DESIGN.md` (or run `context-loader` first).

2. Understand codebase
   - Analyze local code structure with `rg --files`, `rg -n`, and targeted file reads.
   - If `gemini` is available, run repository analysis and save to:
     - `.claude/docs/research/{feature}-codebase.md`
   - If `gemini` is unavailable, create the same file from local analysis.

3. Gather requirements from the user
   - Clarify goal, scope include/exclude, constraints, success criteria, and desired UX.
   - Summarize as a short project brief in the response.

4. Research and constraints
   - Research unresolved points with Gemini when available.
   - Save consolidated findings to:
     - `.claude/docs/research/{feature}.md`
   - Save library-specific findings to:
     - `.claude/docs/libraries/{library}.md` when needed.

5. Design and planning
   - Produce architecture, module boundaries, risks, and mitigations.
   - Create an implementation task plan with dependencies and verification steps.
   - Add a dedicated `Merge Gate` section to `{feature}-plan.md` with:
     - scope include/exclude freeze
     - acceptance criteria
     - key risks and mitigations
     - unresolved questions (if any)
   - Save plan to:
     - `.claude/docs/research/{feature}-plan.md`

6. Merge gate (approval-ready checkpoint)
   - Before implementation, summarize `Merge Gate` in the response using this checklist:
     - `Scope Frozen`: include/exclude is explicit and bounded
     - `Evidence Ready`: research sources/assumptions are listed
     - `Interfaces Locked`: API/schema boundaries are fixed
     - `Quality Gates Defined`: lint/type/test commands are explicit
     - `Risks Accepted`: owner + mitigation is defined for each high risk
   - If any item is not ready, revise plan artifacts first.

7. Persist decisions
   - Update `.claude/docs/DESIGN.md` with key decisions and rationale.

8. Approval gate
   - Present a concise plan summary to the user.
   - Ask for explicit approval before moving to `/team-implement`.

## Command Contract

- `/startproject <feature>`
