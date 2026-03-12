"""Unit tests for startup schema compatibility helpers."""

from unittest.mock import AsyncMock, Mock

import pytest

from app.main import (
    POSTGRES_BIGINT_TIMESTAMP_COLUMNS,
    _ensure_postgresql_bigint_timestamp_columns,
)


@pytest.mark.asyncio
async def test_ensure_postgresql_bigint_timestamp_columns_alters_int4_columns() -> None:
    """PostgreSQL int4 timestamp-ms columns should be promoted to int8."""
    result = Mock()
    result.first.return_value = ("int4",)
    connection = AsyncMock()
    connection.dialect.name = "postgresql"
    side_effects: list[object] = []
    for _ in POSTGRES_BIGINT_TIMESTAMP_COLUMNS:
        side_effects.extend([result, None])
    connection.exec_driver_sql = AsyncMock(side_effect=side_effects)

    await _ensure_postgresql_bigint_timestamp_columns(connection)

    expected_calls = len(POSTGRES_BIGINT_TIMESTAMP_COLUMNS) * 2
    assert connection.exec_driver_sql.await_count == expected_calls


@pytest.mark.asyncio
async def test_ensure_postgresql_bigint_timestamp_columns_is_noop_for_int8() -> None:
    """Already-migrated PostgreSQL columns should not be altered."""
    result = Mock()
    result.first.return_value = ("int8",)
    connection = AsyncMock()
    connection.dialect.name = "postgresql"
    connection.exec_driver_sql = AsyncMock(
        side_effect=[result] * len(POSTGRES_BIGINT_TIMESTAMP_COLUMNS)
    )

    await _ensure_postgresql_bigint_timestamp_columns(connection)

    assert connection.exec_driver_sql.await_count == len(
        POSTGRES_BIGINT_TIMESTAMP_COLUMNS
    )
