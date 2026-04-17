"""Unit tests for lecture QA evaluation helpers."""

from datetime import datetime
from pathlib import Path

from app.evaluation.lecture_qa_eval import (
    EvaluationBackendResult,
    EvaluationScenario,
    RetrievalHit,
    build_transformer_scenarios,
    chunk_transcript_paragraphs,
    evaluate_answer,
    evaluate_offline_bm25_variant,
    render_quantitative_report,
    write_report_artifacts,
)


def test_chunk_transcript_paragraphs_splits_blank_lines() -> None:
    transcript = "first paragraph\n\nsecond paragraph\n\nthird paragraph"
    assert chunk_transcript_paragraphs(transcript) == [
        "first paragraph",
        "second paragraph",
        "third paragraph",
    ]


def test_build_transformer_scenarios_returns_five_cases() -> None:
    scenarios = build_transformer_scenarios(
        transcript_text="dummy",
        qa_notes_text=(
            "Q1. トランスフォーマーはいつ発表された?\n"
            "Q2. トランスフォーマーは誰が発表した?\n"
            "Q2. Googleの研究者等 (Script1より)\n"
            "Q3. トランスフォーマーはどの国で開発された?\n"
            "Q4. どのようなタスクで用いられる?\n"
            "Q5. なぜトレーニング時間が短縮される?\n"
        ),
    )

    assert len(scenarios) == 5
    assert scenarios[0].expected_answer_policy == "fact_exact"
    assert scenarios[1].question == "トランスフォーマーは誰が発表した?"
    assert scenarios[2].expected_no_source is True


def test_hybrid_bm25_outperforms_whitespace_for_japanese_queries() -> None:
    transcript_chunks = [
        "今日はハッシュテーブルについて学習します。ハッシュテーブルはキーと値のペアを高速に検索するデータ構造です。",
        "ハッシュ関数を使ってキーをインデックスに変換し、配列に値を格納します。平均的な検索時間はO(1)です。",
        "ただし、ハッシュ衝突が発生する可能性があります。衝突回避にはチェイン法やオープンアドレス法が使われます。",
    ]
    scenarios = [
        EvaluationScenario(
            case_id="q1",
            question="ハッシュテーブルの検索時間はどのくらいですか",
            expected_evidence_terms=["検索時間", "O(1)"],
            expected_answer_policy="definition_grounded",
            expected_no_source=False,
            expected_answer_terms=["検索時間"],
        ),
        EvaluationScenario(
            case_id="q2",
            question="チェイン法とは何ですか",
            expected_evidence_terms=["チェイン法"],
            expected_answer_policy="definition_grounded",
            expected_no_source=False,
            expected_answer_terms=["チェイン法"],
        ),
    ]

    whitespace = evaluate_offline_bm25_variant(
        variant="bm25_whitespace_current",
        transcript_chunks=transcript_chunks,
        scenarios=scenarios,
    )
    hybrid = evaluate_offline_bm25_variant(
        variant="bm25_hybrid_bigram",
        transcript_chunks=transcript_chunks,
        scenarios=scenarios,
    )

    assert whitespace.metrics["hit@3"] < hybrid.metrics["hit@3"]
    assert hybrid.metrics["hit@1"] >= whitespace.metrics["hit@1"]


def test_write_report_artifacts_creates_history_index(tmp_path: Path) -> None:
    result = EvaluationBackendResult(
        variant="bm25_hybrid_bigram",
        retrieval_backend="bm25_local",
        fallback_used=True,
        post_build_wait_seconds=0,
        cases=[],
        metrics={
            "hit@1": 1.0,
            "hit@3": 1.0,
            "MRR": 1.0,
            "no_source_rate": 0.0,
            "unsupported_answer_rate": 0.0,
            "post_build_no_source_rate": 0.0,
        },
    )
    report = render_quantitative_report(
        run_id="2026-03-10_120000",
        generated_at=datetime(2026, 3, 10, 12, 0, 0),
        results=[result],
    )

    quantitative_path, qualitative_path, index_path = write_report_artifacts(
        output_dir=tmp_path,
        run_id="2026-03-10_120000",
        quantitative_report=report,
        qualitative_report="# qualitative\n",
    )

    assert quantitative_path.exists()
    assert qualitative_path.exists()
    index_text = index_path.read_text(encoding="utf-8")
    assert "2026-03-10_120000_lecture-qa_quantitative.md" in index_text


def test_evaluate_answer_accepts_safe_abstention() -> None:
    scenario = EvaluationScenario(
        case_id="q3",
        question="トランスフォーマーはどの国で開発された?",
        expected_evidence_terms=[],
        expected_answer_policy="abstain_no_source",
        expected_no_source=True,
        expected_answer_terms=[],
    )

    result = evaluate_answer(
        scenario=scenario,
        answer="ソースにそのような情報はない。",
        fallback="ソースにそのような情報はない。",
        confidence="low",
        sources=[RetrievalHit(chunk_id="c1", text="Transformer was published in 2017.", score=1.0)],
    )

    assert result.passed is True
    assert result.failure_reason is None
