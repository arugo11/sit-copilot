"""Unit tests for live caption synthetic replay helpers."""

from datetime import datetime
from pathlib import Path

from app.evaluation.live_caption_replay import (
    ReplayMeasurement,
    render_quantitative_report,
    split_transcript_into_chunks,
    write_report_artifacts,
)


def test_split_transcript_into_chunks_respects_limits() -> None:
    transcript = (
        "First sentence is short. "
        "Second sentence is also short. "
        "Third sentence remains available."
    )

    chunks = split_transcript_into_chunks(
        transcript,
        max_chars=35,
        max_chunks=2,
    )

    assert len(chunks) == 2
    assert chunks[0].index == 1
    assert len(chunks[0].text) <= 35


def test_render_quantitative_report_mentions_ui_path() -> None:
    report = render_quantitative_report(
        run_id="2026-03-10_160000",
        generated_at=datetime(2026, 3, 10, 16, 0, 0),
        source_url="https://example.com/transcript",
        session_id="lec_test",
        inter_chunk_delay_ms=1500,
        measurements=[
            ReplayMeasurement(
                chunk_index=1,
                chars=42,
                text_preview="Hello synthetic replay",
                ingest_http_ms=180.0,
                subtitle_visible_estimate_ms=180.0,
                sse_transcript_final_ms=240.0,
                event_id="evt_1",
            )
        ],
    )

    assert "applyTranscriptFinal" in report
    assert "subtitle_visible_estimate_ms" in report
    assert "sse_transcript_final_ms" in report


def test_write_report_artifacts_creates_live_caption_index(tmp_path: Path) -> None:
    quantitative_path, qualitative_path, index_path = write_report_artifacts(
        output_dir=tmp_path,
        run_id="2026-03-10_160000",
        quantitative_report="# q\n",
        qualitative_report="# qual\n",
    )

    assert quantitative_path.exists()
    assert qualitative_path.exists()
    index_text = index_path.read_text(encoding="utf-8")
    assert "2026-03-10_160000_live-caption_latency.md" in index_text
