"""Deterministic readiness check service."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Protocol

from app.core.config import settings
from app.schemas.readiness import (
    ReadinessCheckRequest,
    ReadinessCheckResponse,
    ReadinessTerm,
)

__all__ = [
    "ReadinessService",
    "DeterministicReadinessService",
]

WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9\-_/]{2,}|[一-龥]{2,}|[ァ-ヴー]{2,}")
SYMBOL_PATTERN = re.compile(r"[=+\-*/^%()<>∑√]")
TOKEN_STOP_WORDS = {
    "する",
    "ため",
    "こと",
    "これ",
    "それ",
    "ます",
    "です",
    "the",
    "and",
    "for",
    "with",
    "from",
    "this",
    "that",
    "course",
}
DEFAULT_TERMS = [
    "講義目標",
    "評価方法",
    "前提知識",
    "重要用語",
    "演習課題",
    "復習計画",
    "理解確認",
    "質問準備",
    "資料確認",
    "学習時間",
]
DEFAULT_DIFFICULT_POINTS = [
    "初回から専門用語がまとまって提示される可能性があります。",
    "評価条件の理解不足が学習計画の遅れにつながる可能性があります。",
]
DEFAULT_RECOMMENDED_SETTINGS = [
    "字幕ON",
    "やさしい日本語要約",
]
DEFAULT_PREP_TASKS = [
    "シラバスの評価方法と提出物の締切を先に整理する。",
    "初回講義で出そうな用語を10語だけ先に確認する。",
]


@dataclass(frozen=True)
class ReadinessSignal:
    """Difficulty signal definition for deterministic scoring."""

    keywords: tuple[str, ...]
    score_delta: int
    difficult_point: str
    recommended_setting: str
    prep_task: str


SIGNALS: tuple[ReadinessSignal, ...] = (
    ReadinessSignal(
        keywords=("数式", "微分", "積分", "線形代数", "統計", "回帰", "行列", "最適化"),
        score_delta=12,
        difficult_point="数式や記号の扱いが多く、板書追従が難しくなる可能性があります。",
        recommended_setting="板書OCRON",
        prep_task="主要な数式記号の意味を10分で復習する。",
    ),
    ReadinessSignal(
        keywords=("発表", "プレゼン", "口頭", "ディスカッション", "討論"),
        score_delta=10,
        difficult_point="口頭説明や発表場面が多く、聞き取り負荷が高くなる可能性があります。",
        recommended_setting="字幕ON",
        prep_task="発表で使う頻出表現を短く音読して慣れておく。",
    ),
    ReadinessSignal(
        keywords=("前提", "履修済", "基礎知識", "必修", "Prerequisite"),
        score_delta=10,
        difficult_point="前提知識を前提に進む可能性があり、導入理解に差が出る可能性があります。",
        recommended_setting="やさしい日本語要約",
        prep_task="前提科目の要点を15分で確認する。",
    ),
    ReadinessSignal(
        keywords=("レポート", "課題", "論述", "essay", "report"),
        score_delta=8,
        difficult_point="記述課題の比重が高く、要点整理に時間が必要になる可能性があります。",
        recommended_setting="用語説明を詳細表示",
        prep_task="評価ルーブリックを先に確認し、提出物の形式を把握する。",
    ),
)


class ReadinessService(Protocol):
    """Interface for readiness check service."""

    async def check(self, request: ReadinessCheckRequest) -> ReadinessCheckResponse:
        """Evaluate readiness and return a deterministic guidance payload."""
        ...


class DeterministicReadinessService:
    """Deterministic readiness scoring and guidance service."""

    async def check(self, request: ReadinessCheckRequest) -> ReadinessCheckResponse:
        normalized_text = _normalize_text(request.syllabus_text)
        score = _compute_score(request, normalized_text)
        terms = _build_terms(
            course_name=request.course_name,
            syllabus_text=normalized_text,
            lang_mode=request.lang_mode,
        )
        difficult_points = _build_difficult_points(normalized_text)
        recommended_settings = _build_recommended_settings(request, normalized_text)
        prep_tasks = _build_prep_tasks(normalized_text)

        return ReadinessCheckResponse(
            readiness_score=score,
            terms=terms,
            difficult_points=difficult_points,
            recommended_settings=recommended_settings,
            prep_tasks=prep_tasks,
            disclaimer=settings.readiness_default_disclaimer,
        )


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def _compute_score(request: ReadinessCheckRequest, syllabus_text: str) -> int:
    score = 40
    text_length = len(syllabus_text)
    if text_length >= 3000:
        score += 12
    elif text_length >= 1500:
        score += 8
    elif text_length >= 800:
        score += 4

    symbol_density = _calc_symbol_density(syllabus_text)
    if symbol_density >= 0.03:
        score += 10
    elif symbol_density >= 0.015:
        score += 6

    for signal in SIGNALS:
        if _contains_any_keyword(syllabus_text, signal.keywords):
            score += signal.score_delta

    if request.jp_level_self is not None:
        if request.jp_level_self <= 2:
            score += 12
        elif request.jp_level_self == 3:
            score += 6
        elif request.jp_level_self >= 5:
            score -= 3

    if request.domain_level_self is not None:
        if request.domain_level_self <= 2:
            score += 12
        elif request.domain_level_self == 3:
            score += 6
        elif request.domain_level_self >= 5:
            score -= 3

    if request.first_material_blob_path:
        score += 3

    return max(0, min(100, score))


def _calc_symbol_density(text: str) -> float:
    if not text:
        return 0.0
    symbol_count = len(SYMBOL_PATTERN.findall(text))
    return symbol_count / len(text)


def _contains_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    normalized_text = text.lower()
    return any(keyword.lower() in normalized_text for keyword in keywords)


def _build_terms(
    *,
    course_name: str,
    syllabus_text: str,
    lang_mode: str,
) -> list[ReadinessTerm]:
    tokens = WORD_PATTERN.findall(f"{course_name} {syllabus_text}")
    normalized_tokens = [
        token.strip()
        for token in tokens
        if token.strip() and token.lower() not in TOKEN_STOP_WORDS
    ]
    counter = Counter(normalized_tokens)
    unique_terms: list[str] = [term for term, _ in counter.most_common()]

    fallback_terms = [term for term in DEFAULT_TERMS if term not in unique_terms]
    selected_terms = unique_terms[: settings.readiness_terms_max_items]
    if len(selected_terms) < settings.readiness_terms_min_items:
        needed = settings.readiness_terms_min_items - len(selected_terms)
        selected_terms.extend(fallback_terms[:needed])

    if len(selected_terms) > settings.readiness_terms_max_items:
        selected_terms = selected_terms[: settings.readiness_terms_max_items]

    return [
        ReadinessTerm(
            term=term,
            explanation=_build_term_explanation(term, lang_mode),
        )
        for term in selected_terms
    ]


def _build_term_explanation(term: str, lang_mode: str) -> str:
    if lang_mode == "en":
        return f"{term} is a core concept to understand before the lecture."
    if lang_mode == "easy-ja":
        return f"{term} は授業で何度も出る大事なことばです。"
    return f"{term} は授業理解に必要な基本用語です。"


def _build_difficult_points(syllabus_text: str) -> list[str]:
    points: list[str] = [
        signal.difficult_point
        for signal in SIGNALS
        if _contains_any_keyword(syllabus_text, signal.keywords)
    ]
    return _fit_text_list(
        values=points,
        defaults=DEFAULT_DIFFICULT_POINTS,
    )


def _build_recommended_settings(
    request: ReadinessCheckRequest,
    syllabus_text: str,
) -> list[str]:
    settings_list: list[str] = [
        signal.recommended_setting
        for signal in SIGNALS
        if _contains_any_keyword(syllabus_text, signal.keywords)
    ]
    if request.jp_level_self is not None and request.jp_level_self <= 3:
        settings_list.append("やさしい日本語要約")
    if request.lang_mode == "en":
        settings_list.append("英語モード")
    return _fit_text_list(
        values=settings_list,
        defaults=DEFAULT_RECOMMENDED_SETTINGS,
    )


def _build_prep_tasks(syllabus_text: str) -> list[str]:
    tasks: list[str] = [
        signal.prep_task
        for signal in SIGNALS
        if _contains_any_keyword(syllabus_text, signal.keywords)
    ]
    return _fit_text_list(
        values=tasks,
        defaults=DEFAULT_PREP_TASKS,
    )


def _fit_text_list(*, values: list[str], defaults: list[str]) -> list[str]:
    deduplicated: list[str] = []
    for value in [*values, *defaults]:
        normalized = value.strip()
        if not normalized or normalized in deduplicated:
            continue
        deduplicated.append(normalized)

    min_items = settings.readiness_points_min_items
    max_items = settings.readiness_points_max_items

    if len(deduplicated) < min_items:
        for default in defaults:
            normalized_default = default.strip()
            if not normalized_default or normalized_default in deduplicated:
                continue
            deduplicated.append(normalized_default)
            if len(deduplicated) >= min_items:
                break

    return deduplicated[:max_items]
