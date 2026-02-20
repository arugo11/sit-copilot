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

2. Verify generated artifacts
   - Confirm latest files exist:
     - `.claude/checkpoints/*.md`
     - `.claude/checkpoints/*.analyze-prompt.md`
   - Confirm `CLAUDE.md` session history was updated.

3. Analyze skill patterns without Claude subagents
   - Read the generated `.analyze-prompt.md` in the current Codex session.
   - Produce candidate skill patterns with confidence and evidence.
   - Optionally save analysis to:
     - `.claude/docs/research/skill-patterns-{date}.md`

4. Report to user
   - Summarize checkpoint stats and top pattern suggestions.
   - Ask whether to convert high-confidence patterns into new skills now.

## Command Contract

- `/checkpointing`
