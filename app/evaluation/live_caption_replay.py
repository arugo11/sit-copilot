"""Synthetic replay helpers for live-caption latency experiments."""

from __future__ import annotations

import html
import json
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_TRANSCRIPT_SOURCE_URL = (
    "https://www.ted.com/pages/sam-altman-on-the-future-of-ai-and-humanity-transcript"
)
DEFAULT_API_BASE_URL = (
    "https://sit-copilot-api.grayground-578aed68.japaneast.azurecontainerapps.io"
)
DEFAULT_OUTPUT_DIR = "docs/reports/live-caption"
DEFAULT_INTER_CHUNK_DELAY_MS = 1500
DEFAULT_SSE_TIMEOUT_MS = 5000
DEFAULT_MAX_CHARS_PER_CHUNK = 120
DEFAULT_MAX_CHUNKS = 12


@dataclass(frozen=True, slots=True)
class ReplayChunk:
    """One synthetic transcript chunk."""

    index: int
    text: str


@dataclass(frozen=True, slots=True)
class ReplayMeasurement:
    """One chunk replay latency sample."""

    chunk_index: int
    chars: int
    text_preview: str
    ingest_http_ms: float
    subtitle_visible_estimate_ms: float
    sse_transcript_final_ms: float | None
    event_id: str


def percentile(values: list[float], ratio: float) -> float:
    """Calculate a simple percentile."""
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
        "mean": sum(values) / len(values),
        "median": percentile(values, 0.5),
        "p95": percentile(values, 0.95),
    }


def fetch_ted_transcript_text(source_url: str) -> str:
    """Fetch a public TED transcript page and extract paragraph text."""
    request = Request(source_url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urlopen(request, timeout=30).read().decode("utf-8", "ignore")
    paragraphs = re.findall(r"<p>(.*?)</p>", raw, re.S)
    cleaned: list[str] = []
    for paragraph in paragraphs:
        text = html.unescape(re.sub(r"<[^>]+>", "", paragraph))
        normalized = " ".join(text.split()).strip()
        if not normalized:
            continue
        if normalized.startswith("ReThinking with Adam Grant"):
            continue
        cleaned.append(normalized)
    return "\n".join(cleaned)


def split_transcript_into_chunks(
    transcript_text: str,
    *,
    max_chars: int = DEFAULT_MAX_CHARS_PER_CHUNK,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
) -> list[ReplayChunk]:
    """Split transcript text into replay-sized chunks."""
    sentences = [
        part.strip()
        for part in re.split(r"(?<=[.!?。！？])\s+", transcript_text)
        if part.strip()
    ]
    chunks: list[ReplayChunk] = []
    current = ""
    chunk_index = 1

    for sentence in sentences:
        candidate = sentence if not current else f"{current} {sentence}"
        if current and len(candidate) > max_chars:
            chunks.append(ReplayChunk(index=chunk_index, text=current))
            chunk_index += 1
            current = sentence
            if len(chunks) >= max_chunks:
                break
            continue
        current = candidate

    if current and len(chunks) < max_chunks:
        chunks.append(ReplayChunk(index=chunk_index, text=current))

    return chunks


class DemoReplayApiClient:
    """Minimal API client for public demo replay experiments."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._lecture_token = ""

    def bootstrap(self) -> None:
        _, payload = self._request_json(
            path="/api/v4/auth/demo-session",
            method="POST",
        )
        self._lecture_token = str(payload["lecture_token"])

    def lecture_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-Lecture-Token": self._lecture_token,
        }

    def start_session(self, *, course_name: str, lang_mode: str = "ja") -> str:
        _, payload = self._request_json(
            path="/api/v4/lecture/session/start",
            method="POST",
            headers=self.lecture_headers(),
            payload={
                "course_name": course_name,
                "course_id": None,
                "lang_mode": lang_mode,
                "camera_enabled": False,
                "slide_roi": None,
                "board_roi": None,
                "consent_acknowledged": True,
            },
        )
        return str(payload["session_id"])

    def finalize_session(self, session_id: str) -> None:
        self._request_json(
            path="/api/v4/lecture/session/finalize",
            method="POST",
            headers=self.lecture_headers(),
            payload={"session_id": session_id, "build_qa_index": False},
        )

    def ingest_speech_chunk(
        self,
        *,
        session_id: str,
        start_ms: int,
        end_ms: int,
        text: str,
    ) -> dict[str, Any]:
        _, payload = self._request_json(
            path="/api/v4/lecture/speech/chunk",
            method="POST",
            headers=self.lecture_headers(),
            payload={
                "session_id": session_id,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "text": text,
                "confidence": 0.95,
                "is_final": True,
                "speaker": "teacher",
            },
        )
        return payload

    def _request_json(
        self,
        *,
        path: str,
        method: str,
        headers: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        url = f"{self._base_url}{path}"
        request_headers = dict(headers or {})
        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        request = Request(
            url=url,
            data=body,
            headers=request_headers,
            method=method,
        )
        with urlopen(request, timeout=30) as response:
            status = int(getattr(response, "status", 200))
            payload_json = json.loads(response.read().decode("utf-8"))
        return status, payload_json


class TranscriptSseCollector:
    """Collect transcript.final events for replay timing."""

    def __init__(self, *, base_url: str, lecture_token: str, session_id: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._lecture_token = lecture_token
        self._session_id = session_id
        self._lock = threading.Condition()
        self._received_at: dict[str, float] = {}
        self._response = None
        self._stopped = False
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stopped = True
        response = self._response
        if response is not None:
            response.close()
        self._thread.join(timeout=1.0)

    def wait_for_event(self, event_id: str, timeout_ms: int) -> float | None:
        deadline = time.perf_counter() + (timeout_ms / 1000.0)
        with self._lock:
            while time.perf_counter() < deadline:
                if event_id in self._received_at:
                    return self._received_at[event_id]
                remaining = max(0.0, deadline - time.perf_counter())
                self._lock.wait(timeout=remaining)
        return None

    def _run(self) -> None:
        params = urlencode({"session_id": self._session_id})
        url = f"{self._base_url}/api/v4/lecture/events/stream?{params}"
        request = Request(
            url=url,
            headers={"X-Lecture-Token": self._lecture_token},
            method="GET",
        )
        try:
            with urlopen(request, timeout=60) as response:
                self._response = response
                raw_lines: list[str] = []
                for line in response:
                    if self._stopped:
                        return
                    decoded = line.decode("utf-8", "ignore").rstrip("\n")
                    if decoded == "":
                        self._process_event(raw_lines)
                        raw_lines = []
                        continue
                    if decoded.startswith(":"):
                        continue
                    raw_lines.append(decoded)
        except Exception:
            return

    def _process_event(self, raw_lines: list[str]) -> None:
        if not raw_lines:
            return
        payload_lines = [
            line[5:].strip()
            for line in raw_lines
            if line.startswith("data:")
        ]
        if not payload_lines:
            return
        try:
            event = json.loads("\n".join(payload_lines))
        except json.JSONDecodeError:
            return
        if event.get("type") != "transcript.final":
            return
        payload = event.get("payload", {})
        event_id = str(payload.get("id", "")).strip()
        if not event_id:
            return
        with self._lock:
            self._received_at[event_id] = time.perf_counter()
            self._lock.notify_all()


def run_synthetic_replay(
    *,
    api_base_url: str,
    transcript_chunks: list[ReplayChunk],
    inter_chunk_delay_ms: int = DEFAULT_INTER_CHUNK_DELAY_MS,
    sse_timeout_ms: int = DEFAULT_SSE_TIMEOUT_MS,
) -> tuple[str, list[ReplayMeasurement]]:
    """Replay transcript chunks through the live caption ingest API."""
    client = DemoReplayApiClient(api_base_url)
    client.bootstrap()
    session_id = client.start_session(course_name="Synthetic Replay Caption Latency")
    collector = TranscriptSseCollector(
        base_url=api_base_url,
        lecture_token=client.lecture_headers()["X-Lecture-Token"],
        session_id=session_id,
    )
    collector.start()
    time.sleep(0.5)

    measurements: list[ReplayMeasurement] = []
    timeline_ms = 0
    try:
        for chunk in transcript_chunks:
            send_started = time.perf_counter()
            response = client.ingest_speech_chunk(
                session_id=session_id,
                start_ms=timeline_ms,
                end_ms=timeline_ms + inter_chunk_delay_ms,
                text=chunk.text,
            )
            http_received = time.perf_counter()
            event_id = str(response["event_id"])
            sse_received_at = collector.wait_for_event(event_id, timeout_ms=sse_timeout_ms)

            ingest_http_ms = (http_received - send_started) * 1000.0
            sse_ms = (
                None
                if sse_received_at is None
                else (sse_received_at - send_started) * 1000.0
            )
            preview = chunk.text[:72].replace("\n", " ")
            measurements.append(
                ReplayMeasurement(
                    chunk_index=chunk.index,
                    chars=len(chunk.text),
                    text_preview=preview,
                    ingest_http_ms=ingest_http_ms,
                    subtitle_visible_estimate_ms=ingest_http_ms,
                    sse_transcript_final_ms=sse_ms,
                    event_id=event_id,
                )
            )
            timeline_ms += inter_chunk_delay_ms
            time.sleep(inter_chunk_delay_ms / 1000.0)
    finally:
        try:
            client.finalize_session(session_id)
        except Exception:
            pass
        collector.stop()

    return session_id, measurements


def render_quantitative_report(
    *,
    run_id: str,
    generated_at: datetime,
    source_url: str,
    session_id: str,
    measurements: list[ReplayMeasurement],
    inter_chunk_delay_ms: int,
) -> str:
    """Render quantitative latency report."""
    http_values = [sample.ingest_http_ms for sample in measurements]
    visible_values = [sample.subtitle_visible_estimate_ms for sample in measurements]
    sse_values = [
        sample.sse_transcript_final_ms
        for sample in measurements
        if sample.sse_transcript_final_ms is not None
    ]
    http_summary = summarize(http_values)
    visible_summary = summarize(visible_values)
    sse_summary = summarize(sse_values)
    sse_coverage = 0.0 if not measurements else len(sse_values) / len(measurements)

    lines = [
        "# Live Caption Synthetic Replay Latency Report",
        "",
        f"- Run ID: `{run_id}`",
        f"- Generated At: `{generated_at.isoformat()}`",
        f"- Session ID: `{session_id}`",
        f"- Source URL: `{source_url}`",
        f"- Chunks Replayed: `{len(measurements)}`",
        f"- Inter-chunk Delay: `{inter_chunk_delay_ms}ms`",
        "",
        "## Interpretation",
        "",
        "- 現在の UI は speech recognition の最終結果を `/speech/chunk` へ送信し、その HTTP 応答直後に `applyTranscriptFinal(...)` で字幕を表示します。",
        "- そのため本実験の `subtitle_visible_estimate_ms` は、現行実装における字幕表示遅延の推定値として `ingest_http_ms` と同値です。",
        "- `sse_transcript_final_ms` はサーバー配信の整合確認用で、ローカル表示より遅くても UI の一次表示には直結しません。",
        "",
        "## Summary",
        "",
        "| Metric | Count | Min (ms) | Median (ms) | Mean (ms) | P95 (ms) | Max (ms) |",
        "|---|---:|---:|---:|---:|---:|---:|",
        "| ingest_http_ms | {count:.0f} | {min:.1f} | {median:.1f} | {mean:.1f} | {p95:.1f} | {max:.1f} |".format(
            **http_summary
        ),
        "| subtitle_visible_estimate_ms | {count:.0f} | {min:.1f} | {median:.1f} | {mean:.1f} | {p95:.1f} | {max:.1f} |".format(
            **visible_summary
        ),
        "| sse_transcript_final_ms | {count:.0f} | {min:.1f} | {median:.1f} | {mean:.1f} | {p95:.1f} | {max:.1f} |".format(
            **sse_summary
        ),
        "",
        f"- SSE coverage: `{sse_coverage:.2%}`",
        "",
        "## Samples",
        "",
        "| Chunk | Chars | ingest_http_ms | subtitle_visible_estimate_ms | sse_transcript_final_ms | Preview |",
        "|---:|---:|---:|---:|---:|---|",
    ]
    for sample in measurements:
        sse_cell = (
            f"{sample.sse_transcript_final_ms:.1f}"
            if sample.sse_transcript_final_ms is not None
            else "-"
        )
        lines.append(
            "| {chunk} | {chars} | {http:.1f} | {visible:.1f} | {sse} | {preview} |".format(
                chunk=sample.chunk_index,
                chars=sample.chars,
                http=sample.ingest_http_ms,
                visible=sample.subtitle_visible_estimate_ms,
                sse=sse_cell,
                preview=sample.text_preview.replace("|", "/"),
            )
        )
    lines.append("")
    return "\n".join(lines)


def render_qualitative_report(
    *,
    run_id: str,
    generated_at: datetime,
    source_url: str,
    measurements: list[ReplayMeasurement],
) -> str:
    """Render qualitative synthetic replay notes."""
    lines = [
        "# Live Caption Synthetic Replay Qualitative Report",
        "",
        f"- Run ID: `{run_id}`",
        f"- Generated At: `{generated_at.isoformat()}`",
        f"- Source URL: `{source_url}`",
        "",
        "## Notes",
        "",
        "- この replay は公開 transcript を synthetic に再送する実験であり、ブラウザ `SpeechRecognition` 自体の音声認識遅延は含みません。",
        "- 含まれるのは、`/speech/chunk` API 応答までの往復と、必要に応じた SSE 再配信の遅延です。",
        "- 実ユーザー体験では、最終字幕の一次表示は HTTP 応答に強く依存します。",
        "",
        "## Chunk Comments",
        "",
        "| Chunk | Comment |",
        "|---:|---|",
    ]
    for sample in measurements:
        if sample.sse_transcript_final_ms is None:
            comment = "HTTP 応答では表示可能だが、SSE 再配信は観測タイムアウト内に未着。"
        elif sample.sse_transcript_final_ms <= sample.ingest_http_ms * 1.2:
            comment = "HTTP と SSE がほぼ同等で、同期は安定。"
        else:
            comment = "HTTP 一次表示は速いが、SSE 側は後追い。再接続整合に注意。"
        lines.append(f"| {sample.chunk_index} | {comment} |")
    lines.append("")
    return "\n".join(lines)


def write_report_artifacts(
    *,
    output_dir: Path,
    run_id: str,
    quantitative_report: str,
    qualitative_report: str,
) -> tuple[Path, Path, Path]:
    """Write live caption report files and update index."""
    output_dir.mkdir(parents=True, exist_ok=True)
    quantitative_path = output_dir / f"{run_id}_live-caption_latency.md"
    qualitative_path = output_dir / f"{run_id}_live-caption_qualitative.md"
    index_path = output_dir / "index.md"

    quantitative_path.write_text(quantitative_report, encoding="utf-8")
    qualitative_path.write_text(qualitative_report, encoding="utf-8")

    if index_path.exists():
        links = re.findall(
            r"\[([^\]]+)\]\(([^)]+)\)",
            index_path.read_text(encoding="utf-8"),
        )
    else:
        links = []

    ordered = [
        (quantitative_path.name, quantitative_path.name),
        (qualitative_path.name, qualitative_path.name),
    ]
    seen = {name for name, _ in ordered}
    for name, target in links:
        if name in seen:
            continue
        ordered.append((name, target))
        seen.add(name)

    history = ["# Live Caption Evaluation Reports", ""]
    history.extend(f"- [{name}]({target})" for name, target in ordered)
    history.append("")
    index_path.write_text("\n".join(history), encoding="utf-8")
    return quantitative_path, qualitative_path, index_path
