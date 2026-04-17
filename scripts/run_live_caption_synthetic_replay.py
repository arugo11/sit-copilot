#!/usr/bin/env python3
"""Run a synthetic replay experiment for live caption latency."""

from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

from app.evaluation.live_caption_replay import (
    DEFAULT_API_BASE_URL,
    DEFAULT_INTER_CHUNK_DELAY_MS,
    DEFAULT_MAX_CHARS_PER_CHUNK,
    DEFAULT_MAX_CHUNKS,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SSE_TIMEOUT_MS,
    DEFAULT_TRANSCRIPT_SOURCE_URL,
    fetch_ted_transcript_text,
    render_qualitative_report,
    render_quantitative_report,
    run_synthetic_replay,
    split_transcript_into_chunks,
    write_report_artifacts,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run synthetic replay for live caption latency."
    )
    parser.add_argument(
        "--api-base-url",
        default=os.environ.get("LIVE_CAPTION_EVAL_API_BASE_URL", DEFAULT_API_BASE_URL),
        help="Lecture API base URL.",
    )
    parser.add_argument(
        "--source-url",
        default=os.environ.get(
            "LIVE_CAPTION_EVAL_SOURCE_URL",
            DEFAULT_TRANSCRIPT_SOURCE_URL,
        ),
        help="Public transcript source URL.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.environ.get("LIVE_CAPTION_EVAL_OUTPUT_DIR", DEFAULT_OUTPUT_DIR),
        help="Output directory for markdown reports.",
    )
    parser.add_argument(
        "--inter-chunk-delay-ms",
        type=int,
        default=int(
            os.environ.get(
                "LIVE_CAPTION_EVAL_INTER_CHUNK_DELAY_MS",
                str(DEFAULT_INTER_CHUNK_DELAY_MS),
            )
        ),
        help="Delay between replayed chunks.",
    )
    parser.add_argument(
        "--sse-timeout-ms",
        type=int,
        default=int(
            os.environ.get(
                "LIVE_CAPTION_EVAL_SSE_TIMEOUT_MS",
                str(DEFAULT_SSE_TIMEOUT_MS),
            )
        ),
        help="Wait timeout for transcript.final SSE event.",
    )
    parser.add_argument(
        "--max-chars-per-chunk",
        type=int,
        default=int(
            os.environ.get(
                "LIVE_CAPTION_EVAL_MAX_CHARS_PER_CHUNK",
                str(DEFAULT_MAX_CHARS_PER_CHUNK),
            )
        ),
        help="Maximum characters per replay chunk.",
    )
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=int(
            os.environ.get(
                "LIVE_CAPTION_EVAL_MAX_CHUNKS",
                str(DEFAULT_MAX_CHUNKS),
            )
        ),
        help="Maximum number of chunks to replay.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    transcript_text = fetch_ted_transcript_text(args.source_url)
    transcript_chunks = split_transcript_into_chunks(
        transcript_text,
        max_chars=args.max_chars_per_chunk,
        max_chunks=args.max_chunks,
    )
    session_id, measurements = run_synthetic_replay(
        api_base_url=args.api_base_url,
        transcript_chunks=transcript_chunks,
        inter_chunk_delay_ms=args.inter_chunk_delay_ms,
        sse_timeout_ms=args.sse_timeout_ms,
    )

    generated_at = datetime.now()
    run_id = generated_at.strftime("%Y-%m-%d_%H%M%S")
    quantitative_report = render_quantitative_report(
        run_id=run_id,
        generated_at=generated_at,
        source_url=args.source_url,
        session_id=session_id,
        measurements=measurements,
        inter_chunk_delay_ms=args.inter_chunk_delay_ms,
    )
    qualitative_report = render_qualitative_report(
        run_id=run_id,
        generated_at=generated_at,
        source_url=args.source_url,
        measurements=measurements,
    )
    quantitative_path, qualitative_path, index_path = write_report_artifacts(
        output_dir=project_root / args.output_dir,
        run_id=run_id,
        quantitative_report=quantitative_report,
        qualitative_report=qualitative_report,
    )
    print(quantitative_path)
    print(qualitative_path)
    print(index_path)


if __name__ == "__main__":
    main()
