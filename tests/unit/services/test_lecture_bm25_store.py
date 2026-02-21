"""Unit tests for LectureBM25Store in-memory index cache."""

import asyncio
from datetime import UTC, datetime

import pytest

from app.services.lecture_bm25_store import LectureBM25Store


class TestLectureBM25StoreBasicOperations:
    """Tests for basic put/get/delete/has operations."""

    @pytest.mark.asyncio
    async def test_put_and_get_index(self) -> None:
        """Store and retrieve BM25 index."""
        store = LectureBM25Store()
        chunks = [
            {"id": "chunk-1", "text": "Hello world"},
            {"id": "chunk-2", "text": "Test content"},
        ]
        tokenized_corpus = [["hello", "world"], ["test", "content"]]
        index_version = "v1"

        await store.put("session-1", chunks, tokenized_corpus, index_version)

        result = await store.get("session-1")

        assert result is not None
        assert result.session_id == "session-1"
        assert result.chunks == chunks
        assert result.tokenized_corpus == tokenized_corpus
        assert result.index_version == "v1"
        assert result.chunk_map == {"chunk-1": chunks[0], "chunk-2": chunks[1]}
        assert isinstance(result.created_at, datetime)

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self) -> None:
        """Getting non-existent session should return None."""
        store = LectureBM25Store()
        result = await store.get("nonexistent-session")
        assert result is None

    @pytest.mark.asyncio
    async def test_put_replaces_existing_index(self) -> None:
        """Putting same session_id should replace existing index."""
        store = LectureBM25Store()
        chunks1 = [{"id": "chunk-1", "text": "Original"}]
        tokenized1 = [["original"]]
        await store.put("session-1", chunks1, tokenized1, "v1")

        # Replace with new data
        chunks2 = [{"id": "chunk-2", "text": "Updated"}]
        tokenized2 = [["updated"]]
        await store.put("session-1", chunks2, tokenized2, "v2")

        result = await store.get("session-1")
        assert result is not None
        assert result.chunks == chunks2
        assert result.tokenized_corpus == tokenized2
        assert result.index_version == "v2"

    @pytest.mark.asyncio
    async def test_delete_index(self) -> None:
        """Remove index from store."""
        store = LectureBM25Store()
        chunks = [{"id": "chunk-1", "text": "Data"}]
        await store.put("session-1", chunks, [["data"]], "v1")

        # Verify exists before delete
        assert await store.has_index("session-1") is True

        await store.delete("session-1")

        # Verify removed
        assert await store.has_index("session-1") is False
        assert await store.get("session-1") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_is_noop(self) -> None:
        """Deleting non-existent session should not raise."""
        store = LectureBM25Store()
        # Should not raise
        await store.delete("nonexistent-session")

    @pytest.mark.asyncio
    async def test_has_index(self) -> None:
        """Check existence of index."""
        store = LectureBM25Store()
        chunks = [{"id": "chunk-1", "text": "Data"}]

        assert await store.has_index("session-1") is False

        await store.put("session-1", chunks, [["data"]], "v1")
        assert await store.has_index("session-1") is True

        await store.delete("session-1")
        assert await store.has_index("session-1") is False


class TestLectureBM25StoreConcurrentOperations:
    """Tests for concurrent access and thread safety."""

    @pytest.mark.asyncio
    async def test_concurrent_get_operations(self) -> None:
        """Multiple concurrent reads should work correctly."""
        store = LectureBM25Store()
        chunks = [{"id": "chunk-1", "text": "Shared data"}]
        await store.put("session-1", chunks, [["shared", "data"]], "v1")

        # Concurrent reads
        results = await asyncio.gather(
            store.get("session-1"),
            store.get("session-1"),
            store.get("session-1"),
            store.get("session-1"),
            store.get("session-1"),
        )

        # All should succeed
        assert all(r is not None for r in results)
        assert all(r.session_id == "session-1" for r in results)  # type: ignore

    @pytest.mark.asyncio
    async def test_concurrent_put_operations(self) -> None:
        """Concurrent writes should be serialized by lock."""
        store = LectureBM25Store()

        async def put_session(session_num: int) -> str:
            chunks = [{"id": f"chunk-{session_num}", "text": f"Data {session_num}"}]
            tokenized = [["data", str(session_num)]]
            version = f"v{session_num}"
            await store.put(f"session-{session_num}", chunks, tokenized, version)
            return version

        # Concurrent writes to different sessions
        results = await asyncio.gather(
            put_session(1),
            put_session(2),
            put_session(3),
            put_session(4),
            put_session(5),
        )

        assert sorted(results) == ["v1", "v2", "v3", "v4", "v5"]

        # Verify all stored correctly
        assert await store.has_index("session-1")
        assert await store.has_index("session-2")
        assert await store.has_index("session-3")
        assert await store.has_index("session-4")
        assert await store.has_index("session-5")


class TestLectureBM25StoreLockManagement:
    """Tests for lock acquisition and management."""

    @pytest.mark.asyncio
    async def test_acquire_lock(self) -> None:
        """Lock acquisition should return usable lock."""
        store = LectureBM25Store()
        lock = await store.acquire_lock("session-1")

        assert isinstance(lock, asyncio.Lock)

        # Lock should be functional
        acquired = lock.locked()
        assert acquired is False  # Not locked yet

        # Test we can acquire it
        async with lock:
            assert lock.locked() is True

    @pytest.mark.asyncio
    async def test_acquire_lock_returns_same_lock(self) -> None:
        """Subsequent calls should return same lock instance."""
        store = LectureBM25Store()

        lock1 = await store.acquire_lock("session-1")
        lock2 = await store.acquire_lock("session-1")

        # Should be the same lock object
        assert lock1 is lock2

    @pytest.mark.asyncio
    async def test_acquire_lock_for_different_sessions(self) -> None:
        """Different sessions should have different locks."""
        store = LectureBM25Store()

        lock1 = await store.acquire_lock("session-1")
        lock2 = await store.acquire_lock("session-2")

        # Should be different lock objects
        assert lock1 is not lock2

        # Acquiring one should not block the other
        async with lock1:
            assert lock1.locked() is True
            assert lock2.locked() is False

    @pytest.mark.asyncio
    async def test_lock_prevents_concurrent_modification(self) -> None:
        """Session lock should serialize modifications."""
        store = LectureBM25Store()
        execution_order = []

        async def modify_with_lock(session_id: str, delay: float) -> None:
            lock = await store.acquire_lock(session_id)
            async with lock:
                execution_order.append(f"start-{session_id}")
                await asyncio.sleep(delay)
                execution_order.append(f"end-{session_id}")

        # Run concurrent operations on same session
        await asyncio.gather(
            modify_with_lock("session-1", 0.01),
            modify_with_lock("session-1", 0.01),
        )

        # Should be serialized (start-end-start-end, not start-start-end-end)
        assert execution_order == [
            "start-session-1",
            "end-session-1",
            "start-session-1",
            "end-session-1",
        ]


class TestLectureBM25StoreChunkMap:
    """Tests for chunk_map functionality."""

    @pytest.mark.asyncio
    async def test_chunk_map_lookup(self) -> None:
        """Verify chunk_map is built correctly for lookup."""
        store = LectureBM25Store()
        chunks = [
            {"id": "chunk-a", "text": "First", "extra": "meta1"},
            {"id": "chunk-b", "text": "Second", "extra": "meta2"},
            {"id": "chunk-c", "text": "Third", "extra": "meta3"},
        ]
        tokenized = [["first"], ["second"], ["third"]]

        await store.put("session-1", chunks, tokenized, "v1")

        index = await store.get("session-1")
        assert index is not None

        # Test chunk_map lookups
        assert index.chunk_map["chunk-a"] == chunks[0]
        assert index.chunk_map["chunk-b"] == chunks[1]
        assert index.chunk_map["chunk-c"] == chunks[2]

        # Verify it's a proper mapping
        assert index.chunk_map["chunk-a"]["extra"] == "meta1"
        assert index.chunk_map["chunk-b"]["extra"] == "meta2"
        assert index.chunk_map["chunk-c"]["extra"] == "meta3"

    @pytest.mark.asyncio
    async def test_chunk_map_updated_on_replace(self) -> None:
        """chunk_map should reflect updated data after put replace."""
        store = LectureBM25Store()
        chunks1 = [{"id": "old-chunk", "text": "Old"}]
        await store.put("session-1", chunks1, [["old"]], "v1")

        # Verify old chunk_map
        index1 = await store.get("session-1")
        assert index1 is not None
        assert "old-chunk" in index1.chunk_map
        assert "new-chunk" not in index1.chunk_map

        # Replace with new chunks
        chunks2 = [{"id": "new-chunk", "text": "New"}]
        await store.put("session-1", chunks2, [["new"]], "v2")

        # Verify new chunk_map
        index2 = await store.get("session-1")
        assert index2 is not None
        assert "old-chunk" not in index2.chunk_map
        assert "new-chunk" in index2.chunk_map
        assert index2.chunk_map["new-chunk"]["text"] == "New"


class TestLectureBM25IndexDataclass:
    """Tests for LectureBM25Index dataclass."""

    @pytest.mark.asyncio
    async def test_index_fields_set_correctly(self) -> None:
        """All fields should be set correctly on creation."""
        store = LectureBM25Store()
        chunks = [{"id": "c1", "text": "Test"}]
        tokenized = [["test"]]

        await store.put("s1", chunks, tokenized, "v1")

        index = await store.get("s1")
        assert index is not None

        assert index.session_id == "s1"
        assert index.chunks == chunks
        assert index.tokenized_corpus == tokenized
        assert index.index_version == "v1"
        assert isinstance(index.created_at, datetime)
        assert index.created_at.tzinfo == UTC

    @pytest.mark.asyncio
    async def test_created_at_is_utc(self) -> None:
        """created_at should be in UTC timezone."""
        store = LectureBM25Store()
        chunks = [{"id": "c1", "text": "Test"}]

        before = datetime.now(UTC)
        await store.put("s1", chunks, [["test"]], "v1")
        after = datetime.now(UTC)

        index = await store.get("s1")
        assert index is not None
        assert before <= index.created_at <= after


class TestLectureBM25StoreEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_chunks_list(self) -> None:
        """Store should handle empty chunks list."""
        store = LectureBM25Store()
        await store.put("session-1", [], [], "v1")

        result = await store.get("session-1")
        assert result is not None
        assert result.chunks == []
        assert result.tokenized_corpus == []
        assert result.chunk_map == {}

    @pytest.mark.asyncio
    async def test_multiple_sessions_independent(self) -> None:
        """Multiple sessions should be stored independently."""
        store = LectureBM25Store()

        await store.put("s1", [{"id": "c1", "text": "A"}], [["a"]], "v1")
        await store.put("s2", [{"id": "c2", "text": "B"}], [["b"]], "v2")
        await store.put("s3", [{"id": "c3", "text": "C"}], [["c"]], "v3")

        assert await store.has_index("s1")
        assert await store.has_index("s2")
        assert await store.has_index("s3")

        # Deleting one should not affect others
        await store.delete("s2")

        assert await store.has_index("s1")
        assert await store.has_index("s2") is False
        assert await store.has_index("s3")

    @pytest.mark.asyncio
    async def test_lock_removed_on_delete(self) -> None:
        """Lock should be removed when session is deleted."""
        store = LectureBM25Store()

        # Create lock by putting index
        await store.put("session-1", [{"id": "c1", "text": "X"}], [["x"]], "v1")
        lock1 = await store.acquire_lock("session-1")

        await store.delete("session-1")

        # New lock should be different object
        lock2 = await store.acquire_lock("session-1")
        assert lock1 is not lock2
