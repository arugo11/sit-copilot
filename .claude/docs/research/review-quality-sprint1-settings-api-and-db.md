# Quality Review: sprint1-settings-api-and-db

## Summary
- Reviewed architecture alignment, maintainability, and behavior against Sprint1 goals.
- Found 2 Medium issues and 1 Low issue.

## Findings

- [Medium] `app/api/v4/settings.py:14`
  - Endpoint behavior is pinned to `DEMO_USER_ID = "demo_user"` for both GET/POST.
  - This makes all callers share the same settings row, so `/me` semantics are not truly per-user.
  - Recommendation: Add an injectable user context provider now (even mock/default), so replacing auth later does not require router/service contract changes.

- [Medium] `app/main.py:23`
  - Schema creation is executed on every startup via `Base.metadata.create_all`.
  - This is acceptable for demo bootstrap but weak for evolution; schema drift and migration gaps can be hidden until runtime.
  - Recommendation: Keep bootstrap behind explicit dev/demo flag and move normal schema management to migrations.

- [Low] `app/core/errors.py:46`
  - `HTTPException` normalization collapses all HTTP errors to code `http_error`.
  - This reduces error taxonomy clarity for clients.
  - Recommendation: Map known status classes (400/404/409/500) to stable domain codes.
