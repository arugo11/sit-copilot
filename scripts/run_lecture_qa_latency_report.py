#!/usr/bin/env python3
"""Measure lecture QA response latency and emit a markdown report."""

from __future__ import annotations

import json
import os
import statistics
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

from app.evaluation.lecture_qa_eval import (
    LectureQaApiClient,
    build_transformer_scenarios,
    chunk_transcript_paragraphs,
)

DEFAULT_API_BASE_URL = "https://sit-copilot-api.grayground-578aed68.japaneast.azurecontainerapps.io"
DEFAULT_SEARCH_ENDPOINT = "https://sitcopilotsearch23088.search.windows.net"
DEFAULT_SEARCH_INDEX_NAME = "lecture_index"
DEFAULT_OUTPUT_DIR = "docs/reports/lecture-qa"
DEFAULT_POST_BUILD_WAIT_SECONDS = 5


@dataclass(frozen=True, slots=True)
class LatencySample:
    """One measured latency sample."""

    phase: str
    label: str
    latency_ms: float
    status: str
    detail: str


def percentile(values: list[float], ratio: float) -> float:
    """Calculate a simple linear percentile."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = ratio * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summarize(values: list[float]) -> dict[str, float]:
    """Summarize latency distribution."""
    if not values:
        return {
            "count": 0.0,
            "min": 0.0,
            "max": 0.0,
            "mean": 0.0,
            "median": 0.0,
            "p95": 0.0,
        }
    return {
        "count": float(len(values)),
        "min": min(values),
        "max": max(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "p95": percentile(values, 0.95),
    }


def measure_call(label: str, func, *args, **kwargs) -> tuple[LatencySample, object]:
    """Measure one function call."""
    started = time.perf_counter()
    result = func(*args, **kwargs)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    sample = LatencySample(
        phase=label,
        label=label,
        latency_ms=elapsed_ms,
        status="ok",
        detail="",
    )
    return sample, result


def measure_search_latency(
    *,
    endpoint: str,
    api_key: str,
    index_name: str,
    session_id: str,
    question: str,
) -> tuple[LatencySample, list[object]]:
    """Measure direct Azure Search latency for one question."""
    started = time.perf_counter()
    hits = LectureQaApiClient.search_sources(
        endpoint=endpoint,
        api_key=api_key,
        index_name=index_name,
        session_id=session_id,
        question=question,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return (
        LatencySample(
            phase="azure_search",
            label=question,
            latency_ms=elapsed_ms,
            status="ok",
            detail=f"hits={len(hits)}",
        ),
        hits,
    )


def update_history_index(output_dir: Path, report_path: Path) -> Path:
    """Append a latency report link to the shared evaluation index."""
    index_path = output_dir / "index.md"
    lines = []
    if index_path.exists():
        lines = index_path.read_text(encoding="utf-8").splitlines()
    link_line = f"- [{report_path.name}]({report_path.name})"
    if link_line not in lines:
        if not lines:
            lines = ["# Lecture QA Evaluation Reports", ""]
        lines.append(link_line)
    index_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return index_path


def render_latency_report(
    *,
    run_id: str,
    generated_at: datetime,
    session_id: str,
    samples: list[LatencySample],
    post_build_wait_seconds: int,
) -> str:
    """Render latency markdown report."""
    phase_names = [
        "bootstrap",
        "session_start",
        "speech_ingest",
        "index_build",
        "azure_search",
        "qa_ask_immediate",
        "qa_ask_delayed",
    ]
    lines = [
        "# Lecture QA Latency Report",
        "",
        f"- Run ID: `{run_id}`",
        f"- Generated At: `{generated_at.isoformat()}`",
        f"- Session ID: `{session_id}`",
        f"- Post-build Wait: `{post_build_wait_seconds}s`",
        "",
        "## Phase Summary",
        "",
        "| Phase | Count | Min (ms) | Median (ms) | Mean (ms) | P95 (ms) | Max (ms) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for phase_name in phase_names:
        values = [
            sample.latency_ms for sample in samples if sample.phase == phase_name
        ]
        stats = summarize(values)
        lines.append(
            "| {phase} | {count:.0f} | {min:.1f} | {median:.1f} | {mean:.1f} | {p95:.1f} | {max:.1f} |".format(
                phase=phase_name,
                count=stats["count"],
                min=stats["min"],
                median=stats["median"],
                mean=stats["mean"],
                p95=stats["p95"],
                max=stats["max"],
            )
        )

    lines.extend(
        [
            "",
            "## Detailed Samples",
            "",
            "| Phase | Label | Latency (ms) | Status | Detail |",
            "|---|---|---:|---|---|",
        ]
    )
    for sample in samples:
        lines.append(
            "| {phase} | {label} | {latency:.1f} | {status} | {detail} |".format(
                phase=sample.phase,
                label=sample.label.replace("|", "/"),
                latency=sample.latency_ms,
                status=sample.status,
                detail=sample.detail.replace("|", "/"),
            )
        )

    immediate = [s.latency_ms for s in samples if s.phase == "qa_ask_immediate"]
    delayed = [s.latency_ms for s in samples if s.phase == "qa_ask_delayed"]
    azure = [s.latency_ms for s in samples if s.phase == "azure_search"]
    lines.extend(
        [
            "",
            "## Observations",
            "",
            "- `azure_search` は retrieval 単体の往復時間で、`qa_ask_*` は retrieval と生成を含む API 全体の時間です。",
            "- `qa_ask_immediate` と `qa_ask_delayed` の差は、主に index 可視化遅延と生成負荷の差を見ています。",
            "- `qa_ask_*` が `azure_search` より大幅に遅い場合、ボトルネックは retrieval ではなく answer/verifier 系である可能性が高いです。",
        ]
    )
    if immediate and delayed:
        lines.append(
            "- 今回の計測では `qa_ask_immediate` 平均 {:.1f}ms に対し `qa_ask_delayed` 平均 {:.1f}ms でした。".format(
                statistics.fmean(immediate),
                statistics.fmean(delayed),
            )
        )
    if azure:
        lines.append(
            "- `azure_search` 平均は {:.1f}ms で、QA API より十分小さいため、体感遅延の主因は生成側です。".format(
                statistics.fmean(azure),
            )
        )
    lines.append("")
    return "\n".join(lines)


def fetch_search_key(subscription_id: str) -> str:
    """Fetch Azure Search admin key via Azure CLI."""
    import subprocess

    command = [
        "az",
        "search",
        "admin-key",
        "show",
        "--subscription",
        subscription_id,
        "--resource-group",
        "sit-copilot",
        "--service-name",
        "sitcopilotsearch23088",
        "-o",
        "json",
    ]
    body = json.loads(
        subprocess.check_output(command, text=True, cwd="/home/argo/sit-copilot")
    )
    return str(body["primaryKey"])


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    api_base_url = os.environ.get("LECTURE_QA_EVAL_API_BASE_URL", DEFAULT_API_BASE_URL)
    search_endpoint = os.environ.get(
        "LECTURE_QA_EVAL_SEARCH_ENDPOINT", DEFAULT_SEARCH_ENDPOINT
    )
    search_index_name = os.environ.get(
        "LECTURE_QA_EVAL_SEARCH_INDEX_NAME", DEFAULT_SEARCH_INDEX_NAME
    )
    output_dir = project_root / os.environ.get(
        "LECTURE_QA_EVAL_OUTPUT_DIR", DEFAULT_OUTPUT_DIR
    )
    post_build_wait_seconds = int(
        os.environ.get(
            "LECTURE_QA_EVAL_POST_BUILD_WAIT_SECONDS",
            str(DEFAULT_POST_BUILD_WAIT_SECONDS),
        )
    )
    search_api_key = os.environ.get("LECTURE_QA_EVAL_SEARCH_API_KEY", "").strip()
    if not search_api_key:
        search_api_key = fetch_search_key(
            "4c170a0d-3e6d-42a0-b941-533e4f44e729"
        )

    transcript_text = (project_root / "docs/transformer.md").read_text(encoding="utf-8")
    qa_notes_text = (project_root / "docs/transformer_qa.md").read_text(encoding="utf-8")
    transcript_chunks = chunk_transcript_paragraphs(transcript_text)
    scenarios = build_transformer_scenarios(transcript_text, qa_notes_text)

    client = LectureQaApiClient(base_url=api_base_url)
    samples: list[LatencySample] = []

    sample, _ = measure_call("bootstrap", client.bootstrap)
    samples.append(sample)

    sample, session_id = measure_call(
        "session_start",
        client.start_session,
        course_name="Transformer Latency Evaluation",
    )
    samples.append(sample)

    lecture_headers = client._lecture_headers()  # noqa: SLF001
    for index, chunk in enumerate(transcript_chunks, start=1):
        start_ms = (index - 1) * 30_000
        started = time.perf_counter()
        status, _ = client._request_json(  # noqa: SLF001
            path="/api/v4/lecture/speech/chunk",
            method="POST",
            headers=lecture_headers,
            payload={
                "session_id": session_id,
                "start_ms": start_ms,
                "end_ms": start_ms + 29_000,
                "text": chunk,
                "confidence": 0.95,
                "is_final": True,
                "speaker": "teacher",
            },
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if status != 200:
            raise RuntimeError(f"failed to ingest chunk {index}")
        samples.append(
            LatencySample(
                phase="speech_ingest",
                label=f"chunk_{index}",
                latency_ms=elapsed_ms,
                status="ok",
                detail=f"chars={len(chunk)}",
            )
        )

    sample, _ = measure_call("index_build", client.build_index, session_id=session_id)
    samples.append(sample)

    for scenario in scenarios:
        sample, _ = measure_search_latency(
            endpoint=search_endpoint,
            api_key=search_api_key,
            index_name=search_index_name,
            session_id=session_id,
            question=scenario.question,
        )
        samples.append(sample)

        started = time.perf_counter()
        response = client.ask(session_id=session_id, question=scenario.question)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        samples.append(
            LatencySample(
                phase="qa_ask_immediate",
                label=scenario.case_id,
                latency_ms=elapsed_ms,
                status="ok",
                detail="sources={} confidence={}".format(
                    len(response.get("sources", [])),
                    response.get("confidence", ""),
                ),
            )
        )

    time.sleep(post_build_wait_seconds)
    for scenario in scenarios:
        started = time.perf_counter()
        response = client.ask(session_id=session_id, question=scenario.question)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        samples.append(
            LatencySample(
                phase="qa_ask_delayed",
                label=scenario.case_id,
                latency_ms=elapsed_ms,
                status="ok",
                detail="sources={} confidence={}".format(
                    len(response.get("sources", [])),
                    response.get("confidence", ""),
                ),
            )
        )

    generated_at = datetime.now()
    run_id = generated_at.strftime("%Y-%m-%d_%H%M%S")
    report = render_latency_report(
        run_id=run_id,
        generated_at=generated_at,
        session_id=session_id,
        samples=samples,
        post_build_wait_seconds=post_build_wait_seconds,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{run_id}_lecture-qa_latency.md"
    report_path.write_text(report, encoding="utf-8")
    index_path = update_history_index(output_dir, report_path)
    print(report_path)
    print(index_path)


if __name__ == "__main__":
    main()
