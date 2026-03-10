#!/usr/bin/env python3
"""Repair persisted summary windows by rebuilding them per session."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import delete, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]

REBUILDABLE_SESSION_STATUSES = {"active", "live", "finalized"}
DEFAULT_MAX_REBUILD_WINDOWS = 1_200


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Delete and rebuild summary_windows for target sessions. "
            "Default mode=local avoids Azure LLM usage."
        )
    )
    parser.add_argument(
        "--all-sessions",
        action="store_true",
        help="Repair all sessions.",
    )
    parser.add_argument(
        "--session-id",
        action="append",
        default=[],
        help="Target session ID (repeatable).",
    )
    parser.add_argument(
        "--mode",
        choices=["local", "azure"],
        default="local",
        help="Summary generation mode used for rebuild.",
    )
    parser.add_argument(
        "--max-rebuild-windows",
        type=int,
        default=DEFAULT_MAX_REBUILD_WINDOWS,
        help="Maximum windows rebuilt per session.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned operations without writing to DB.",
    )
    args = parser.parse_args()
    if not args.all_sessions and not args.session_id:
        parser.error("Specify --all-sessions or at least one --session-id.")
    return args


def build_generator(mode: str, settings):
    """Build summary generator for repair mode."""
    from app.services.lecture_summary_generator_service import (
        AzureOpenAILectureSummaryGeneratorService,
        ResilientLectureSummaryGeneratorService,
        UnavailableLectureSummaryGeneratorService,
    )

    fallback = UnavailableLectureSummaryGeneratorService(
        reason="repair_summary_windows_local_mode"
    )
    if mode == "local":
        return fallback
    primary = AzureOpenAILectureSummaryGeneratorService(
        api_key=settings.azure_openai_api_key,
        endpoint=settings.azure_openai_endpoint,
        account_name=settings.azure_openai_account_name,
        model=settings.azure_openai_model,
        keyterms_model=settings.azure_openai_keyterms_model,
    )
    return ResilientLectureSummaryGeneratorService(
        primary=primary,
        fallback=fallback,
    )


def _normalize_session_ids(raw_ids: list[str]) -> list[str]:
    """Normalize and deduplicate session IDs while preserving order."""
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in raw_ids:
        session_id = raw.strip()
        if not session_id or session_id in seen:
            continue
        normalized.append(session_id)
        seen.add(session_id)
    return normalized


async def _load_target_sessions(
    *,
    session_model,
    async_session_factory,
    all_sessions: bool,
    session_ids: list[str],
) -> list[object]:
    """Load target sessions to repair."""
    async with async_session_factory() as db:
        stmt = select(session_model)
        if not all_sessions:
            stmt = stmt.where(session_model.id.in_(session_ids))
        stmt = stmt.order_by(session_model.started_at)
        result = await db.execute(stmt)
        return list(result.scalars().all())


async def run() -> int:
    """Run summary window repair."""
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from app.core.config import settings
    from app.db.session import AsyncSessionFactory, commit_with_retry
    from app.models.lecture_session import LectureSession
    from app.models.summary_window import SummaryWindow
    from app.services.lecture_summary_service import SqlAlchemyLectureSummaryService

    args = parse_args()
    session_ids = _normalize_session_ids(args.session_id)
    sessions = await _load_target_sessions(
        session_model=LectureSession,
        async_session_factory=AsyncSessionFactory,
        all_sessions=args.all_sessions,
        session_ids=session_ids,
    )
    if not sessions:
        print("No matching sessions found.")
        return 1

    mode = args.mode
    generator = build_generator(mode, settings)
    max_rebuild_windows = max(1, args.max_rebuild_windows)
    print(
        f"Repair start: sessions={len(sessions)} mode={mode} "
        f"max_rebuild_windows={max_rebuild_windows} dry_run={args.dry_run}"
    )

    repaired = 0
    skipped = 0
    failed = 0

    async with AsyncSessionFactory() as db:
        service = SqlAlchemyLectureSummaryService(
            db=db,
            summary_generator=generator,
            max_rebuild_windows=max_rebuild_windows,
        )
        for session in sessions:
            if session.status not in REBUILDABLE_SESSION_STATUSES:
                skipped += 1
                print(
                    f"Skip session_id={session.id} "
                    f"status={session.status} (not rebuildable)"
                )
                continue

            if args.dry_run:
                print(f"Dry-run session_id={session.id} status={session.status}")
                continue

            try:
                await db.execute(
                    delete(SummaryWindow).where(SummaryWindow.session_id == session.id)
                )
                await commit_with_retry(db)
                rebuilt_count = await service.rebuild_windows(
                    session_id=session.id,
                    user_id=session.user_id,
                )
                await commit_with_retry(db)
                repaired += 1
                print(
                    f"Repaired session_id={session.id} "
                    f"status={session.status} summary_windows={rebuilt_count}"
                )
            except Exception as exc:  # pragma: no cover - operational safety
                await db.rollback()
                failed += 1
                print(
                    f"Failed session_id={session.id} "
                    f"status={session.status} error={exc.__class__.__name__}"
                )

    print(f"Repair done: repaired={repaired} skipped={skipped} failed={failed}")
    return 2 if failed else 0


def main() -> int:
    """CLI entrypoint."""
    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
