"""Unit tests for lecture key terms service."""

import json

import pytest

from app.services.lecture_keyterms_service import (
    AzureOpenAILectureKeyTermsService,
    UnavailableLectureKeyTermsService,
)


@pytest.mark.asyncio
async def test_unavailable_keyterms_service_returns_empty_result() -> None:
    """Unavailable key terms fallback should not emit pseudo terms."""
    service = UnavailableLectureKeyTermsService(
        reason="azure openai key terms backend is unavailable"
    )

    result = await service.extract_key_terms(
        transcript_text="などの時系列データを扱って翻訳します",
        lang_mode="ja",
    )

    assert result.key_terms == []
    assert result.detected_terms == []


def test_parse_response_filters_terms_not_in_transcript() -> None:
    """Extractor should keep only terms that literally appear in transcript."""
    service = AzureOpenAILectureKeyTermsService(
        api_key="dummy",
        endpoint="https://example.openai.azure.com/",
        model="dummy-model",
    )

    transcript = (
        "Transformer（トランスフォーマー）は、2017年6月12日にGoogleの研究者等が"
        "発表した深層学習モデルであり、主に自然言語処理（NLP）の分野で使用される。"
    )
    response_json = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "key_terms": [
                                {
                                    "term": "Transformer（トランスフォーマー）",
                                    "explanation": "説明",
                                    "translation": "とらんすふぉーまー",
                                },
                                {
                                    "term": "自己注意機構",
                                    "explanation": "説明",
                                    "translation": "じこちゅういきこう",
                                },
                            ],
                            "detected_terms": [
                                "Transformer（トランスフォーマー）",
                                "自己注意機構",
                            ],
                        },
                        ensure_ascii=False,
                    )
                }
            }
        ]
    }

    result = service._parse_response(response_json, transcript_text=transcript)  # noqa: SLF001

    assert [item["term"] for item in result.key_terms] == [
        "Transformer（トランスフォーマー）"
    ]
    assert result.detected_terms == ["Transformer（トランスフォーマー）"]
