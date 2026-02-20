# Quality Review Report: f0-readiness-check

## Scope

- `app/api/v4/readiness.py`
- `app/schemas/readiness.py`
- `app/services/readiness_service.py`
- integration with `app/main.py`

## Summary

- Critical: 0
- High: 0
- Medium: 1
- Low: 0

## Findings

### Medium

1. English keyword detection is case-sensitive and can miss expected signals.
- File: `app/services/readiness_service.py:94`
- File: `app/services/readiness_service.py:196`
- File: `app/services/readiness_service.py:257`
- Detail:
  - Difficulty signal list includes English tokens (e.g., `"Prerequisite"`, `"essay"`, `"report"`).
  - Matching uses direct substring checks without case normalization (`_contains_any_keyword`).
  - Inputs such as `"prerequisite"` (lowercase) will not match `"Prerequisite"`, causing under-scoring and missing guidance in English syllabus text.
- Recommended fix:
  - Normalize matching to case-insensitive comparison for ASCII keywords, e.g., lower-case both text and keyword during matching.
  - Keep Japanese keyword behavior unchanged.

## Notes

- Module boundaries and DI wiring align with existing architecture.
- Type annotations and schema constraints are consistent with current codebase style.
