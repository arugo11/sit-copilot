"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    app_name: str = "SIT Copilot"
    version: str = "0.1.0"
    debug: bool = False
    database_url: str = "sqlite+aiosqlite:///./sit_copilot.db"
    procedure_api_token: str = "dev-procedure-token"
    lecture_api_token: str = "dev-lecture-token"
    lecture_visual_max_image_bytes: int = 2_000_000
    lecture_qa_retrieval_limit: int = 5
    azure_openai_enabled: bool = False
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_model: str = "gpt-4o"
    azure_search_enabled: bool = False
    azure_search_api_key: str = ""
    azure_search_endpoint: str = ""
    azure_search_index_name: str = "lecture_index"
    procedure_retrieval_limit: int = 3
    procedure_query_max_length: int = 512
    procedure_no_source_fallback: str = (
        "現在の質問に対応する公式根拠が見つかりませんでした。"
    )
    procedure_no_source_action_next: str = (
        "教務課または公式ポータルで最新の手続き情報を確認してください。"
    )

    model_config = {
        "env_file": (".env", ".env.azure.generated"),
        "extra": "ignore",
    }


settings = Settings()
