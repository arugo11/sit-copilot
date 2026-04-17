"""Lecture QA evaluation helpers and report generation."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from rank_bm25 import BM25Okapi

from app.services.lecture_retrieval_service import (
    tokenize_hybrid_japanese_text,
    tokenize_whitespace_text,
)

ExpectedAnswerPolicy = Literal[
    "fact_exact",
    "definition_grounded",
    "abstain_no_source",
    "multi_fact_grounded",
]
EvaluationVariant = Literal[
    "azure_only",
    "azure_plus_local_fallback_immediate",
    "azure_plus_local_fallback_delayed",
    "bm25_whitespace_current",
    "bm25_hybrid_bigram",
]

ABSTAIN_PATTERNS = (
    "資料にない",
    "資料に記載がありません",
    "講義資料に該当する情報が見つかりませんでした",
    "確認できません",
    "ソースにそのような情報はない",
)


@dataclass(frozen=True, slots=True)
class EvaluationScenario:
    """Normalized lecture QA scenario derived from doc notes."""

    case_id: str
    question: str
    expected_evidence_terms: list[str]
    expected_answer_policy: ExpectedAnswerPolicy
    expected_no_source: bool
    expected_answer_terms: list[str]


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    """Retrieved source candidate for evaluation."""

    chunk_id: str
    text: str
    score: float


@dataclass(frozen=True, slots=True)
class AnswerEvaluation:
    """Evaluated answer outcome."""

    passed: bool
    failure_reason: str | None
    subjective_scores: dict[str, int]
    comment: str


@dataclass(frozen=True, slots=True)
class CaseEvaluation:
    """Per-case result for a single backend/variant."""

    scenario: EvaluationScenario
    retrieved_sources: list[RetrievalHit]
    answer: str
    fallback: str | None
    confidence: str | None
    retrieval_pass_at_1: bool
    retrieval_pass_at_3: bool
    reciprocal_rank: float
    answer_evaluation: AnswerEvaluation


@dataclass(frozen=True, slots=True)
class EvaluationBackendResult:
    """Aggregate evaluation result for one backend."""

    variant: EvaluationVariant
    retrieval_backend: str
    fallback_used: bool
    post_build_wait_seconds: int
    cases: list[CaseEvaluation]
    metrics: dict[str, float]


def chunk_transcript_paragraphs(transcript_text: str) -> list[str]:
    """Split memo transcript into paragraph-sized ASR chunks."""
    chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", transcript_text) if chunk.strip()]
    return chunks


def build_transformer_scenarios(
    transcript_text: str,
    qa_notes_text: str,
) -> list[EvaluationScenario]:
    """Build normalized transformer evaluation scenarios from memo docs."""
    _ = transcript_text
    lines = [line.strip() for line in qa_notes_text.splitlines() if line.strip()]
    questions: dict[str, str] = {}
    for line in lines:
        match = re.match(r"Q(\d+)\.\s*(.+)", line)
        if match:
            questions.setdefault(match.group(1), match.group(2).strip())

    return [
        EvaluationScenario(
            case_id="transformer_q1",
            question=questions.get("1", "トランスフォーマーはいつ発表された?"),
            expected_evidence_terms=["2017年6月12日"],
            expected_answer_policy="fact_exact",
            expected_no_source=False,
            expected_answer_terms=["2017年6月12日"],
        ),
        EvaluationScenario(
            case_id="transformer_q2",
            question=questions.get("2", "トランスフォーマーは誰が発表した?"),
            expected_evidence_terms=["Googleの研究者"],
            expected_answer_policy="fact_exact",
            expected_no_source=False,
            expected_answer_terms=["Googleの研究者"],
        ),
        EvaluationScenario(
            case_id="transformer_q3",
            question=questions.get("3", "トランスフォーマーはどの国で開発された?"),
            expected_evidence_terms=[],
            expected_answer_policy="abstain_no_source",
            expected_no_source=True,
            expected_answer_terms=[],
        ),
        EvaluationScenario(
            case_id="transformer_q4",
            question=questions.get("4", "どのようなタスクで用いられる?"),
            expected_evidence_terms=["翻訳", "テキスト要約", "時系列データ"],
            expected_answer_policy="multi_fact_grounded",
            expected_no_source=False,
            expected_answer_terms=["翻訳", "テキスト要約"],
        ),
        EvaluationScenario(
            case_id="transformer_q5",
            question=questions.get("5", "なぜトレーニング時間が短縮される?"),
            expected_evidence_terms=["逐次処理する必要がない", "並列化"],
            expected_answer_policy="definition_grounded",
            expected_no_source=False,
            expected_answer_terms=["逐次処理する必要がない"],
        ),
    ]


def evaluate_offline_bm25_variant(
    *,
    variant: EvaluationVariant,
    transcript_chunks: list[str],
    scenarios: list[EvaluationScenario],
) -> EvaluationBackendResult:
    """Evaluate offline retrieval quality using BM25 over memo transcript chunks."""
    tokenizer = (
        tokenize_hybrid_japanese_text
        if variant == "bm25_hybrid_bigram"
        else tokenize_whitespace_text
    )
    tokenized_corpus = [tokenizer(chunk) for chunk in transcript_chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    cases: list[CaseEvaluation] = []

    for scenario in scenarios:
        query_tokens = tokenizer(scenario.question)
        scores = [float(score) for score in bm25.get_scores(query_tokens)]
        ranked = sorted(
            enumerate(scores),
            key=lambda item: item[1],
            reverse=True,
        )
        hits = [
            RetrievalHit(
                chunk_id=f"chunk-{index + 1}",
                text=transcript_chunks[index],
                score=score,
            )
            for index, score in ranked[:3]
            if score > 0.0
        ]
        answer_text = _build_offline_answer_stub(scenario, hits)
        answer_eval = evaluate_answer(
            scenario=scenario,
            answer=answer_text,
            fallback=answer_text,
            confidence="low" if scenario.expected_no_source else "medium",
            sources=hits,
        )
        cases.append(
            _build_case_evaluation(
                scenario=scenario,
                hits=hits,
                answer=answer_text,
                fallback=answer_text,
                confidence="low" if scenario.expected_no_source else "medium",
                answer_evaluation=answer_eval,
            )
        )

    return EvaluationBackendResult(
        variant=variant,
        retrieval_backend="bm25_local",
        fallback_used=variant == "bm25_hybrid_bigram",
        post_build_wait_seconds=0,
        cases=cases,
        metrics=_summarize_metrics(cases),
    )


def evaluate_answer(
    *,
    scenario: EvaluationScenario,
    answer: str,
    fallback: str | None,
    confidence: str | None,
    sources: list[RetrievalHit],
) -> AnswerEvaluation:
    """Evaluate answer quality with deterministic rubric."""
    normalized_answer = " ".join(answer.split())
    has_sources = bool(sources)
    abstained = _contains_any(normalized_answer, ABSTAIN_PATTERNS)

    if scenario.expected_no_source:
        if abstained:
            return AnswerEvaluation(
                passed=True,
                failure_reason=None,
                subjective_scores={
                    "Groundedness": 5,
                    "Answer completeness": 5,
                    "Abstention quality": 5,
                    "Citation usefulness": 4 if has_sources else 5,
                    "Japanese clarity": 4,
                },
                comment="根拠不足ケースで安全に abstain できている。",
            )
        return AnswerEvaluation(
            passed=False,
            failure_reason="hallucinated_detail",
            subjective_scores={
                "Groundedness": 1,
                "Answer completeness": 1,
                "Abstention quality": 1,
                "Citation usefulness": 2 if has_sources else 1,
                "Japanese clarity": 3,
            },
            comment="根拠不足にもかかわらず断定回答している。",
        )

    matched_terms = [
        term for term in scenario.expected_answer_terms if term in normalized_answer
    ]
    if abstained:
        return AnswerEvaluation(
            passed=False,
            failure_reason="wrong_abstain",
            subjective_scores={
                "Groundedness": 3,
                "Answer completeness": 1,
                "Abstention quality": 1,
                "Citation usefulness": 2 if has_sources else 1,
                "Japanese clarity": 3,
            },
            comment="根拠があるのに abstain している。",
        )
    if matched_terms:
        completeness = 5 if len(matched_terms) == len(scenario.expected_answer_terms) else 4
        return AnswerEvaluation(
            passed=True,
            failure_reason=None,
            subjective_scores={
                "Groundedness": 5 if has_sources else 3,
                "Answer completeness": completeness,
                "Abstention quality": 4,
                "Citation usefulness": 5 if has_sources else 2,
                "Japanese clarity": 4 if confidence != "low" else 3,
            },
            comment="期待する事実要素を含み、根拠に沿っている。",
        )
    failure_reason = "retrieval_miss" if not has_sources else "answerer_failure"
    return AnswerEvaluation(
        passed=False,
        failure_reason=failure_reason,
        subjective_scores={
            "Groundedness": 2 if has_sources else 1,
            "Answer completeness": 1,
            "Abstention quality": 2,
            "Citation usefulness": 2 if has_sources else 1,
            "Japanese clarity": 3,
        },
        comment="期待する事実要素が回答に反映されていない。",
    )


def render_quantitative_report(
    *,
    run_id: str,
    generated_at: datetime,
    results: list[EvaluationBackendResult],
) -> str:
    """Render the quantitative markdown report."""
    lines = [
        "# Lecture QA Quantitative Evaluation",
        "",
        f"- Run ID: `{run_id}`",
        f"- Generated At: `{generated_at.isoformat()}`",
        "",
        "## Backend Summary",
        "",
        "| Variant | Retrieval Backend | Fallback Used | Wait(s) | hit@1 | hit@3 | MRR | no_source_rate | unsupported_answer_rate | post_build_no_source_rate |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        metrics = result.metrics
        lines.append(
            "| {variant} | {backend} | {fallback} | {wait} | {hit1:.2f} | {hit3:.2f} | {mrr:.2f} | {no_source:.2f} | {unsupported:.2f} | {post_build:.2f} |".format(
                variant=result.variant,
                backend=result.retrieval_backend,
                fallback="yes" if result.fallback_used else "no",
                wait=result.post_build_wait_seconds,
                hit1=metrics["hit@1"],
                hit3=metrics["hit@3"],
                mrr=metrics["MRR"],
                no_source=metrics["no_source_rate"],
                unsupported=metrics["unsupported_answer_rate"],
                post_build=metrics["post_build_no_source_rate"],
            )
        )

    for result in results:
        lines.extend(
            [
                "",
                f"## {result.variant}",
                "",
                "| Case | Retrieval Pass@1 | Retrieval Pass@3 | RR | Answer Pass | Failure Reason | Retrieved Sources |",
                "|---|---:|---:|---:|---:|---|---|",
            ]
        )
        for case in result.cases:
            source_ids = ", ".join(source.chunk_id for source in case.retrieved_sources) or "-"
            lines.append(
                "| {case_id} | {hit1} | {hit3} | {rr:.2f} | {answer_pass} | {failure_reason} | {source_ids} |".format(
                    case_id=case.scenario.case_id,
                    hit1="yes" if case.retrieval_pass_at_1 else "no",
                    hit3="yes" if case.retrieval_pass_at_3 else "no",
                    rr=case.reciprocal_rank,
                    answer_pass="yes" if case.answer_evaluation.passed else "no",
                    failure_reason=case.answer_evaluation.failure_reason or "-",
                    source_ids=source_ids,
                )
            )
    return "\n".join(lines) + "\n"


def render_qualitative_report(
    *,
    run_id: str,
    generated_at: datetime,
    results: list[EvaluationBackendResult],
) -> str:
    """Render the qualitative markdown report."""
    lines = [
        "# Lecture QA Qualitative Evaluation",
        "",
        f"- Run ID: `{run_id}`",
        f"- Generated At: `{generated_at.isoformat()}`",
    ]
    for result in results:
        lines.extend(
            [
                "",
                f"## {result.variant}",
                "",
                "| Case | Groundedness | Answer completeness | Abstention quality | Citation usefulness | Japanese clarity | Comment |",
                "|---|---:|---:|---:|---:|---:|---|",
            ]
        )
        for case in result.cases:
            scores = case.answer_evaluation.subjective_scores
            lines.append(
                "| {case_id} | {grounded} | {complete} | {abstain} | {citation} | {clarity} | {comment} |".format(
                    case_id=case.scenario.case_id,
                    grounded=scores["Groundedness"],
                    complete=scores["Answer completeness"],
                    abstain=scores["Abstention quality"],
                    citation=scores["Citation usefulness"],
                    clarity=scores["Japanese clarity"],
                    comment=case.answer_evaluation.comment,
                )
            )
            lines.append("")
            lines.append(f"Answer: {case.answer or '(none)'}")
            if case.retrieved_sources:
                for source in case.retrieved_sources:
                    lines.append(
                        f"- Source `{source.chunk_id}` score={source.score:.3f}: {source.text}"
                    )
            else:
                lines.append("- Source: none")
    return "\n".join(lines) + "\n"


def write_report_artifacts(
    *,
    output_dir: Path,
    run_id: str,
    quantitative_report: str,
    qualitative_report: str,
) -> tuple[Path, Path, Path]:
    """Write markdown reports and update the index file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    quantitative_path = output_dir / f"{run_id}_lecture-qa_quantitative.md"
    qualitative_path = output_dir / f"{run_id}_lecture-qa_qualitative.md"
    index_path = output_dir / "index.md"

    quantitative_path.write_text(quantitative_report, encoding="utf-8")
    qualitative_path.write_text(qualitative_report, encoding="utf-8")

    if index_path.exists():
        existing_links = re.findall(
            r"\[([^\]]+)\]\(([^)]+)\)",
            index_path.read_text(encoding="utf-8"),
        )
    else:
        existing_links = []

    ordered_links: list[tuple[str, str]] = [
        (quantitative_path.name, quantitative_path.name),
        (qualitative_path.name, qualitative_path.name),
    ]
    seen = {name for name, _ in ordered_links}
    for name, target in existing_links:
        if name in seen:
            continue
        ordered_links.append((name, target))
        seen.add(name)

    history_lines = ["# Lecture QA Evaluation Reports", ""]
    history_lines.extend(f"- [{name}]({target})" for name, target in ordered_links)
    history_lines.append("")
    index_path.write_text("\n".join(history_lines), encoding="utf-8")
    return quantitative_path, qualitative_path, index_path


def _build_case_evaluation(
    *,
    scenario: EvaluationScenario,
    hits: list[RetrievalHit],
    answer: str,
    fallback: str | None,
    confidence: str | None,
    answer_evaluation: AnswerEvaluation,
) -> CaseEvaluation:
    rank = _first_relevant_rank(scenario=scenario, hits=hits)
    return CaseEvaluation(
        scenario=scenario,
        retrieved_sources=hits,
        answer=answer,
        fallback=fallback,
        confidence=confidence,
        retrieval_pass_at_1=rank == 1,
        retrieval_pass_at_3=rank > 0 and rank <= 3,
        reciprocal_rank=0.0 if rank == 0 else 1.0 / float(rank),
        answer_evaluation=answer_evaluation,
    )


def _first_relevant_rank(
    *,
    scenario: EvaluationScenario,
    hits: list[RetrievalHit],
) -> int:
    if scenario.expected_no_source:
        return 0
    for index, hit in enumerate(hits, start=1):
        if _source_matches_expected_terms(hit.text, scenario.expected_evidence_terms):
            return index
    return 0


def _source_matches_expected_terms(text: str, terms: list[str]) -> bool:
    if not terms:
        return False
    return any(term in text for term in terms)


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in text for pattern in patterns)


def _build_offline_answer_stub(
    scenario: EvaluationScenario,
    hits: list[RetrievalHit],
) -> str:
    if scenario.expected_no_source:
        return "ソースにそのような情報はない。"
    if not hits:
        return "講義資料に該当する情報が見つかりませんでした。"
    return hits[0].text


def _summarize_metrics(cases: list[CaseEvaluation]) -> dict[str, float]:
    evidence_cases = [case for case in cases if not case.scenario.expected_no_source]
    hit_at_1 = _mean(1.0 if case.retrieval_pass_at_1 else 0.0 for case in evidence_cases)
    hit_at_3 = _mean(1.0 if case.retrieval_pass_at_3 else 0.0 for case in evidence_cases)
    mrr = _mean(case.reciprocal_rank for case in evidence_cases)
    no_source_rate = _mean(1.0 if not case.retrieved_sources else 0.0 for case in cases)
    unsupported_answer_rate = _mean(
        1.0 if not case.answer_evaluation.passed else 0.0 for case in cases
    )
    return {
        "hit@1": hit_at_1,
        "hit@3": hit_at_3,
        "MRR": mrr,
        "no_source_rate": no_source_rate,
        "unsupported_answer_rate": unsupported_answer_rate,
        "post_build_no_source_rate": no_source_rate,
    }


def _mean(values: Any) -> float:
    data = list(values)
    if not data:
        return 0.0
    return sum(data) / float(len(data))


class LectureQaApiClient:
    """Minimal API client for lecture QA evaluation."""

    def __init__(self, *, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._lecture_token: str | None = None
        self._procedure_token: str | None = None

    def bootstrap(self) -> dict[str, str]:
        status, body = self._request_json(
            path="/api/v4/auth/demo-session",
            method="POST",
        )
        if status != 200:
            raise RuntimeError("failed to bootstrap demo session")
        self._lecture_token = str(body["lecture_token"])
        self._procedure_token = str(body["procedure_token"])
        return {
            "lecture_token": self._lecture_token,
            "procedure_token": self._procedure_token,
            "user_id": str(body["user_id"]),
        }

    def start_session(self, *, course_name: str) -> str:
        status, body = self._request_json(
            path="/api/v4/lecture/session/start",
            method="POST",
            headers=self._lecture_headers(),
            payload={
                "course_name": course_name,
                "course_id": None,
                "lang_mode": "ja",
                "camera_enabled": False,
                "slide_roi": None,
                "board_roi": None,
                "consent_acknowledged": True,
            },
        )
        if status != 200:
            raise RuntimeError("failed to start lecture session")
        return str(body["session_id"])

    def ingest_chunks(self, *, session_id: str, chunks: list[str]) -> None:
        for index, chunk in enumerate(chunks):
            start_ms = index * 30_000
            status, _ = self._request_json(
                path="/api/v4/lecture/speech/chunk",
                method="POST",
                headers=self._lecture_headers(),
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
            if status != 200:
                raise RuntimeError("failed to ingest speech chunk")

    def build_index(self, *, session_id: str) -> None:
        status, _ = self._request_json(
            path="/api/v4/lecture/qa/index/build",
            method="POST",
            headers=self._lecture_headers(),
            payload={"session_id": session_id, "rebuild": True},
        )
        if status != 200:
            raise RuntimeError("failed to build lecture qa index")

    def ask(self, *, session_id: str, question: str) -> dict[str, Any]:
        status, body = self._request_json(
            path="/api/v4/lecture/qa/ask",
            method="POST",
            headers=self._lecture_headers(),
            payload={
                "session_id": session_id,
                "question": question,
                "lang_mode": "ja",
                "retrieval_mode": "source-only",
                "top_k": 3,
                "context_window": 1,
            },
        )
        if status != 200:
            raise RuntimeError("failed to ask lecture qa")
        return body

    @staticmethod
    def search_sources(
        *,
        endpoint: str,
        api_key: str,
        index_name: str,
        session_id: str,
        question: str,
    ) -> list[RetrievalHit]:
        url = (
            f"{endpoint.rstrip('/')}/indexes/{index_name}/docs/search?"
            f"api-version=2024-07-01"
        )
        payload = json.dumps(
            {
                "search": question,
                "top": 3,
                "count": True,
                "filter": f"session_id eq '{session_id}'",
                "select": "chunk_id,speech_text,visual_text,summary_text",
            }
        ).encode("utf-8")
        request = Request(
            url=url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "api-key": api_key,
            },
            method="POST",
        )
        with urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))

        hits: list[RetrievalHit] = []
        for item in body.get("value", []):
            if not isinstance(item, dict):
                continue
            text = ""
            for field in ("speech_text", "visual_text", "summary_text"):
                value = item.get(field)
                if isinstance(value, str) and value.strip():
                    text = value.strip()
                    break
            chunk_id = str(item.get("chunk_id", "")).strip()
            if not chunk_id or not text:
                continue
            hits.append(
                RetrievalHit(
                    chunk_id=chunk_id,
                    text=text,
                    score=float(item.get("@search.score", 0.0) or 0.0),
                )
            )
        return hits

    def _lecture_headers(self) -> dict[str, str]:
        if not self._lecture_token:
            raise RuntimeError("bootstrap must be called first")
        return {
            "Content-Type": "application/json",
            "X-Lecture-Token": self._lecture_token,
        }

    def _request_json(
        self,
        *,
        path: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        data = None
        merged_headers = dict(headers or {})
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            merged_headers.setdefault("Content-Type", "application/json")

        request = Request(
            url=f"{self._base_url}{path}",
            data=data,
            headers=merged_headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=60) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8")
            return exc.code, json.loads(body) if body else {}
