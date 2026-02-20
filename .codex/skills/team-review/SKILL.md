---
name: team-review
description: Run multi-perspective review in Codex after implementation (security, quality, and test coverage) without Claude Agent Teams dependency.
---

# Team Review (Codex Native)

Perform structured review passes in one Codex session. No Claude Agent Teams required.

## Prerequisites

- Implementation complete
- Tests runnable in current environment

## Workflow

1. Collect review target
   - Identify diff and changed files:
     - `git diff --name-only <base>...HEAD` when base exists
     - fallback: `git diff --name-only`

2. Run three review passes
   - Security pass: secrets, injection, authz/authn, sensitive logging.
   - Quality pass: architecture drift, complexity, typing, maintainability.
   - Testing pass: missing cases, flaky patterns, coverage gaps.

3. Persist reports
   - Save findings to:
     - `.claude/docs/research/review-security-{feature}.md`
     - `.claude/docs/research/review-quality-{feature}.md`
     - `.claude/docs/research/review-tests-{feature}.md`

4. Synthesize and prioritize
   - Classify as Critical, High, Medium, Low.
   - Provide concrete file references and recommended fixes.

5. User decision
   - Ask whether to apply fixes now or defer low-priority items.

## Command Contract

- `/team-review`
