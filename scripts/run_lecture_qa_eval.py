#!/usr/bin/env python3
"""Run lecture QA evaluation and emit markdown reports."""

from __future__ import annotations

import argparse
import os
import time
from datetime import datetime
from pathlib import Path

from app.evaluation.lecture_qa_eval import (
    EvaluationBackendResult,
    LectureQaApiClient,
    build_transformer_scenarios,
    chunk_transcript_paragraphs,
    evaluate_answer,
    evaluate_offline_bm25_variant,
    render_qualitative_report,
    render_quantitative_report,
    write_report_artifacts,
    _build_case_evaluation,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run lecture QA evaluation.")
    parser.add_argument(
        "--api-base-url",
        default=os.environ.get("LECTURE_QA_EVAL_API_BASE_URL", ""),
        help="Lecture QA API base URL for live E2E evaluation.",
    )
    parser.add_argument(
        "--search-endpoint",
        default=os.environ.get("LECTURE_QA_EVAL_SEARCH_ENDPOINT", ""),
        help="Azure Search endpoint for direct retrieval checks.",
    )
    parser.add_argument(
        "--search-api-key",
        default=os.environ.get("LECTURE_QA_EVAL_SEARCH_API_KEY", ""),
        help="Azure Search admin/query key.",
    )
    parser.add_argument(
        "--search-index-name",
        default=os.environ.get("LECTURE_QA_EVAL_SEARCH_INDEX_NAME", "lecture_index"),
        help="Azure Search lecture index name.",
    )
    parser.add_argument(
        "--output-dir",
        default="docs/reports/lecture-qa",
        help="Output directory for markdown reports.",
    )
    parser.add_argument(
        "--post-build-wait-seconds",
        type=int,
        default=2,
        help="Delay between immediate and delayed ask runs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    transcript_text = (project_root / "docs/transformer.md").read_text(encoding="utf-8")
    qa_notes_text = (project_root / "docs/transformer_qa.md").read_text(encoding="utf-8")
    transcript_chunks = chunk_transcript_paragraphs(transcript_text)
    scenarios = build_transformer_scenarios(transcript_text, qa_notes_text)

    results: list[EvaluationBackendResult] = [
        evaluate_offline_bm25_variant(
            variant="bm25_whitespace_current",
            transcript_chunks=transcript_chunks,
            scenarios=scenarios,
        ),
        evaluate_offline_bm25_variant(
            variant="bm25_hybrid_bigram",
            transcript_chunks=transcript_chunks,
            scenarios=scenarios,
        ),
    ]

    if args.api_base_url and args.search_endpoint and args.search_api_key:
        results.extend(
            run_live_evaluation(
                api_base_url=args.api_base_url,
                search_endpoint=args.search_endpoint,
                search_api_key=args.search_api_key,
                search_index_name=args.search_index_name,
                transcript_chunks=transcript_chunks,
                scenarios=scenarios,
                post_build_wait_seconds=args.post_build_wait_seconds,
            )
        )

    generated_at = datetime.now()
    run_id = generated_at.strftime("%Y-%m-%d_%H%M%S")
    quantitative = render_quantitative_report(
        run_id=run_id,
        generated_at=generated_at,
        results=results,
    )
    qualitative = render_qualitative_report(
        run_id=run_id,
        generated_at=generated_at,
        results=results,
    )
    quantitative_path, qualitative_path, index_path = write_report_artifacts(
        output_dir=project_root / args.output_dir,
        run_id=run_id,
        quantitative_report=quantitative,
        qualitative_report=qualitative,
    )
    print(quantitative_path)
    print(qualitative_path)
    print(index_path)


def run_live_evaluation(
    *,
    api_base_url: str,
    search_endpoint: str,
    search_api_key: str,
    search_index_name: str,
    transcript_chunks: list[str],
    scenarios: list,
    post_build_wait_seconds: int,
) -> list[EvaluationBackendResult]:
    client = LectureQaApiClient(base_url=api_base_url)
    client.bootstrap()
    session_id = client.start_session(course_name="Transformer Evaluation")
    client.ingest_chunks(session_id=session_id, chunks=transcript_chunks)
    client.build_index(session_id=session_id)

    azure_only_cases = []
    immediate_cases = []
    delayed_cases = []

    for scenario in scenarios:
        azure_hits = LectureQaApiClient.search_sources(
            endpoint=search_endpoint,
            api_key=search_api_key,
            index_name=search_index_name,
            session_id=session_id,
            question=scenario.question,
        )
        azure_answer_eval = evaluate_answer(
            scenario=scenario,
            answer=azure_hits[0].text if azure_hits else "",
            fallback=None,
            confidence=None,
            sources=azure_hits,
        )
        azure_only_cases.append(
            _build_case_evaluation(
                scenario=scenario,
                hits=azure_hits,
                answer=azure_hits[0].text if azure_hits else "",
                fallback=None,
                confidence=None,
                answer_evaluation=azure_answer_eval,
            )
        )

        immediate_response = client.ask(session_id=session_id, question=scenario.question)
        immediate_hits = _hits_from_api_response(immediate_response)
        immediate_cases.append(
            _build_case_evaluation(
                scenario=scenario,
                hits=immediate_hits,
                answer=str(immediate_response.get("answer", "")),
                fallback=_to_optional_str(immediate_response.get("fallback")),
                confidence=_to_optional_str(immediate_response.get("confidence")),
                answer_evaluation=evaluate_answer(
                    scenario=scenario,
                    answer=str(immediate_response.get("answer", "")),
                    fallback=_to_optional_str(immediate_response.get("fallback")),
                    confidence=_to_optional_str(immediate_response.get("confidence")),
                    sources=immediate_hits,
                ),
            )
        )

    time.sleep(max(0, post_build_wait_seconds))
    for scenario in scenarios:
        delayed_response = client.ask(session_id=session_id, question=scenario.question)
        delayed_hits = _hits_from_api_response(delayed_response)
        delayed_cases.append(
            _build_case_evaluation(
                scenario=scenario,
                hits=delayed_hits,
                answer=str(delayed_response.get("answer", "")),
                fallback=_to_optional_str(delayed_response.get("fallback")),
                confidence=_to_optional_str(delayed_response.get("confidence")),
                answer_evaluation=evaluate_answer(
                    scenario=scenario,
                    answer=str(delayed_response.get("answer", "")),
                    fallback=_to_optional_str(delayed_response.get("fallback")),
                    confidence=_to_optional_str(delayed_response.get("confidence")),
                    sources=delayed_hits,
                ),
            )
        )

    from app.evaluation.lecture_qa_eval import _summarize_metrics

    return [
        EvaluationBackendResult(
            variant="azure_only",
            retrieval_backend="azure_search",
            fallback_used=False,
            post_build_wait_seconds=0,
            cases=azure_only_cases,
            metrics=_summarize_metrics(azure_only_cases),
        ),
        EvaluationBackendResult(
            variant="azure_plus_local_fallback_immediate",
            retrieval_backend="api_runtime",
            fallback_used=True,
            post_build_wait_seconds=0,
            cases=immediate_cases,
            metrics=_summarize_metrics(immediate_cases),
        ),
        EvaluationBackendResult(
            variant="azure_plus_local_fallback_delayed",
            retrieval_backend="api_runtime",
            fallback_used=True,
            post_build_wait_seconds=post_build_wait_seconds,
            cases=delayed_cases,
            metrics=_summarize_metrics(delayed_cases),
        ),
    ]


def _hits_from_api_response(response: dict[str, object]) -> list:
    from app.evaluation.lecture_qa_eval import RetrievalHit

    hits = []
    for item in response.get("sources", []):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        chunk_id = str(item.get("chunk_id", "")).strip()
        if not text or not chunk_id:
            continue
        hits.append(
            RetrievalHit(
                chunk_id=chunk_id,
                text=text,
                score=float(item.get("bm25_score", 0.0) or 0.0),
            )
        )
    return hits


def _to_optional_str(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


if __name__ == "__main__":
    main()
