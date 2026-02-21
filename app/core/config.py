"""Application configuration using Pydantic Settings."""

import re

from pydantic import Field, field_validator
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
    azure_openai_account_name: str = ""
    azure_openai_model: str = "gpt-4o"
    azure_openai_api_version: str = "2024-02-15-preview"
    azure_speech_key: str = ""
    azure_speech_region: str = ""
    azure_speech_token_expires_in_sec: int = Field(default=540, ge=1, le=600)
    azure_speech_sts_timeout_seconds: int = Field(default=5, ge=1, le=30)
    azure_search_enabled: bool = False
    azure_search_api_key: str = ""
    azure_search_endpoint: str = ""
    azure_search_index_name: str = "lecture_index"
    procedure_search_index_name: str = "procedure_index"
    procedure_retrieval_limit: int = 3
    procedure_query_max_length: int = 512
    procedure_no_source_fallback: str = (
        "現在の質問に対応する公式根拠が見つかりませんでした。"
    )
    procedure_backend_failure_fallback: str = (
        "回答生成中にエラーが発生しました。"
        "教務課または公式ポータルで最新の手続き情報を確認してください。"
    )
    procedure_no_source_action_next: str = (
        "教務課または公式ポータルで最新の手続き情報を確認してください。"
    )
    readiness_course_name_max_length: int = 255
    readiness_syllabus_max_length: int = 20_000
    readiness_blob_path_max_length: int = 1_024
    readiness_terms_min_items: int = 10
    readiness_terms_max_items: int = 20
    readiness_points_min_items: int = 2
    readiness_points_max_items: int = 5
    readiness_default_disclaimer: str = (
        "この結果は履修準備の目安です. 履修可否を判定するものではありません."
    )

    @field_validator("azure_speech_region")
    @classmethod
    def validate_azure_speech_region(cls, value: str) -> str:
        """Normalize and validate Azure Speech region name."""
        normalized = value.strip().lower()
        if not normalized:
            return normalized
        if not re.fullmatch(r"[a-z0-9-]+", normalized):
            raise ValueError("azure_speech_region must contain only a-z, 0-9, '-'.")
        return normalized

    model_config = {
        "env_file": (".env", ".env.azure.generated"),
        "extra": "ignore",
    }


settings = Settings()
