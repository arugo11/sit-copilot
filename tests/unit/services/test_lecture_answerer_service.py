"""Unit tests for lecture answerer Azure OpenAI configuration behavior."""

from app.services.lecture_answerer_service import AzureOpenAILectureAnswererService


def test_is_azure_openai_ready_with_missing_deployment() -> None:
    service = AzureOpenAILectureAnswererService(
        api_key="test-key",
        endpoint="https://test.openai.azure.com/",
        model="",
    )
    assert service._is_azure_openai_ready() is False  # noqa: SLF001


def test_build_chat_completion_url_normalizes_cognitive_endpoint() -> None:
    service = AzureOpenAILectureAnswererService(
        api_key="test-key",
        endpoint="https://japaneast.api.cognitive.microsoft.com/",
        account_name="aoai-test",
        model="gpt-4o",
    )

    result = service._build_chat_completion_url()  # noqa: SLF001
    assert (
        "https://aoai-test.openai.azure.com/openai/deployments/gpt-4o/chat/completions"
        in result
    )
