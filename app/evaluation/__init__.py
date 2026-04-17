"""Evaluation helpers for lecture QA experiments."""

from app.evaluation.lecture_qa_eval import (
    EvaluationBackendResult,
    EvaluationScenario,
    EvaluationVariant,
    build_transformer_scenarios,
    chunk_transcript_paragraphs,
    render_qualitative_report,
    render_quantitative_report,
    write_report_artifacts,
)
from app.evaluation.live_caption_replay import (
    DEFAULT_API_BASE_URL as LIVE_CAPTION_DEFAULT_API_BASE_URL,
    DEFAULT_OUTPUT_DIR as LIVE_CAPTION_DEFAULT_OUTPUT_DIR,
    DEFAULT_TRANSCRIPT_SOURCE_URL as LIVE_CAPTION_DEFAULT_SOURCE_URL,
    ReplayMeasurement,
    fetch_ted_transcript_text,
    render_qualitative_report as render_live_caption_qualitative_report,
    render_quantitative_report as render_live_caption_quantitative_report,
    run_synthetic_replay,
    split_transcript_into_chunks,
    write_report_artifacts as write_live_caption_report_artifacts,
)

__all__ = [
    "EvaluationBackendResult",
    "EvaluationScenario",
    "EvaluationVariant",
    "LIVE_CAPTION_DEFAULT_API_BASE_URL",
    "LIVE_CAPTION_DEFAULT_OUTPUT_DIR",
    "LIVE_CAPTION_DEFAULT_SOURCE_URL",
    "ReplayMeasurement",
    "build_transformer_scenarios",
    "chunk_transcript_paragraphs",
    "fetch_ted_transcript_text",
    "render_qualitative_report",
    "render_quantitative_report",
    "render_live_caption_qualitative_report",
    "render_live_caption_quantitative_report",
    "run_synthetic_replay",
    "split_transcript_into_chunks",
    "write_report_artifacts",
    "write_live_caption_report_artifacts",
]
