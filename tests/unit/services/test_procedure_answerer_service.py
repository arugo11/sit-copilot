"""Unit tests for procedure answerer Azure OpenAI configuration behavior."""

from app.services.procedure_answerer_service import AzureOpenAIProcedureAnswererService


def test_is_azure_openai_ready_with_missing_deployment() -> None:
    service = AzureOpenAIProcedureAnswererService(
        api_key="test-key",
        endpoint="https://sample.openai.azure.com/",
        model="",
    )
    assert service._is_azure_openai_ready() is False  # noqa: SLF001


def test_build_chat_completion_url_uses_normalized_openai_endpoint() -> None:
    service = AzureOpenAIProcedureAnswererService(
        api_key="test-key",
        endpoint="https://japaneast.api.cognitive.microsoft.com/",
        account_name="aoai-test",
        model="gpt-4o",
    )
    result = service._build_chat_completion_url()  # noqa: SLF001
    assert (
        result
        == "https://aoai-test.openai.azure.com/openai/deployments/gpt-4o/chat/completions"
        "?api-version=2024-05-01-preview"
    )
