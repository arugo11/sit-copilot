"""Unit tests for lecture answerer Azure OpenAI behavior."""

from app.schemas.lecture_qa import LectureSource
from app.services.lecture_answerer_service import AzureOpenAILectureAnswererService


def test_is_azure_openai_ready_with_missing_deployment() -> None:
    service = AzureOpenAILectureAnswererService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
        model="",
    )
    assert service._is_azure_openai_ready() is False  # noqa: SLF001


def test_build_chat_completion_url_keeps_cognitive_endpoint() -> None:
    service = AzureOpenAILectureAnswererService(
        api_key="test-key",
        endpoint="https://japaneast.api.cognitive.microsoft.com/",
        account_name="aoai-test",
        model="gpt-4o",
    )

    result = service._build_chat_completion_url()  # noqa: SLF001
    assert (
        "https://japaneast.api.cognitive.microsoft.com/openai/deployments/gpt-4o/chat/completions"
        in result
    )


def test_build_prompt_prefers_english_for_english_question() -> None:
    service = AzureOpenAILectureAnswererService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
        model="gpt-4o",
    )
    sources = [
        LectureSource(
            chunk_id="c1",
            timestamp="00:05",
            text="Lecture mentions supervised learning.",
            type="speech",
            bm25_score=1.0,
            is_direct_hit=True,
        )
    ]

    prompt = service._build_prompt(  # noqa: SLF001
        question="What is supervised learning?",
        lang_mode="ja",
        sources=sources,
        history="",
    )

    assert "Response language: English only" in prompt


def test_build_prompt_uses_easy_japanese_when_lang_mode_is_easy_ja() -> None:
    service = AzureOpenAILectureAnswererService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
        model="gpt-4o",
    )
    sources = [
        LectureSource(
            chunk_id="c1",
            timestamp="00:05",
            text="この講義では教師あり学習について説明しています。",
            type="speech",
            bm25_score=1.0,
            is_direct_hit=True,
        )
    ]

    prompt = service._build_prompt(  # noqa: SLF001
        question="教師あり学習とは何ですか？",
        lang_mode="easy-ja",
        sources=sources,
        history="",
    )

    assert "回答言語: やさしい日本語" in prompt
