---
name: checkpointing
description: Run full session checkpointing from Codex without Claude dependencies. Collect git and CLI activity, generate checkpoint files, update session history, and analyze reusable skill patterns.
---

# Checkpointing (Codex Native)

Use the local checkpoint script directly and perform analysis in the same Codex session.

## Usage

- `/checkpointing`
- `/checkpointing --since YYYY-MM-DD`

## Workflow

1. Run checkpoint collection
   - Command:
     - `python .claude/skills/checkpointing/checkpoint.py`
     - or `python .claude/skills/checkpointing/checkpoint.py --since YYYY-MM-DD`
   - If `python` is unavailable, use:
     - `python3 .claude/skills/checkpointing/checkpoint.py`
     - or `python3 .claude/skills/checkpointing/checkpoint.py --since YYYY-MM-DD`

2. Verify generated artifacts
   - Confirm latest files exist:
     - `.claude/checkpoints/*.md`
     - `.claude/checkpoints/*.analyze-prompt.md`
   - Confirm `CLAUDE.md` session history was updated.
   - Extract the checkpoint UTC timestamp and reuse it for every derived artifact.

3. Analyze skill patterns without Claude subagents
   - Read the generated `.analyze-prompt.md` in the current Codex session.
   - Produce candidate skill patterns with confidence and evidence.
   - Save analysis to:
     - `.claude/docs/research/skill-patterns-{checkpoint-timestamp}.md`
   - Naming convention:
     - Use the same UTC timestamp as checkpoint filename (example: `2026-02-20-225248`).
     - This avoids overwriting date-only reports.

4. Enforce output quality gate
   - Artifact consistency:
     - `checkpoint`, `analyze-prompt`, and `skill-patterns` files all share the same timestamp.
     - New timestamped report is created (`skill-patterns-{timestamp}.md`), not date-only overwrite.
   - Analysis structure (required):
     - `Checkpoint Stats` section exists.
     - `Candidate Patterns` section has at least 3 patterns.
     - Each pattern includes: `Description`, trigger phrases (JA/EN), `Confidence` (0-1), `Evidence`, `Existing skill overlap`.
   - Recommendation quality:
     - Explicitly decide: "create new skill" vs "strengthen existing skill".
     - Prioritize top 1-3 actions by impact and effort.

5. Report to user
   - Summarize checkpoint stats and top pattern suggestions.
   - Include output-quality gate result (pass/fail and missing items if any).
   - Ask whether to convert high-confidence patterns into new skills now.

## Reporting Template

Use this minimal structure in the user-facing report:

1. `Checkpoint result`: branch, commits, tasks completed, generated artifact paths.
2. `Quality gate`: pass/fail with concrete checks performed.
3. `Top pattern suggestions`: top 3 with confidence and overlap note.
4. `Recommended next action`: single clear recommendation.

## Command Contract

- `/checkpointing`
