"""User ID normalization helpers for demo compatibility."""

from __future__ import annotations

DEMO_USER_ID_ALIASES = {"demo-user", "demo_user"}


def get_user_id_candidates(user_id: str) -> set[str]:
    """Return acceptable user-id candidates for ownership checks.

    Keeps strict behavior for normal users, while allowing legacy demo aliases.
    """
    normalized = user_id.strip()
    if normalized in DEMO_USER_ID_ALIASES:
        return set(DEMO_USER_ID_ALIASES)
    return {normalized}
