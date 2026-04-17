"""Application configuration using Pydantic Settings."""

import re
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings


class WeaveSettings(BaseSettings):
    """WandB Weave configuration."""

    # Basic settings
    enabled: bool = Field(default=False, description="Enable Weave tracking (demo mode)")
    project: str = Field(default="sit-copilot-demo")
    entity: str = Field(default="")
    mode: Literal["local", "cloud"] = Field(default="local")

    # Cloud authentication
    api_key: str = Field(default="", alias="wandb_api_key")

    # Data capture (demo: all enabled)
    capture_prompts: bool = Field(default=True)
    capture_responses: bool = Field(default=True)
    capture_images: bool = Field(default=True)
    max_image_size_bytes: int = Field(default=10 * 1024 * 1024)

    # Performance settings
    queue_maxsize: int = Field(default=1000)
    worker_count: int = Field(default=2)
    timeout_ms: int = Field(default=5000)
    sample_rate: float = Field(default=1.0, ge=0, le=1)

    model_config = {
        "env_prefix": "WEAVE_",
        "extra": "ignore",
    }


class Settings(BaseSettings):
    """Application settings."""

    app_name: str = "SIT Copilot"
    version: str = "0.1.0"
    debug: bool = False
    database_url: str = "sqlite+aiosqlite:///./sit_copilot.db"
    azure_subscription_id: str = "4c170a0d-3e6d-42a0-b941-533e4f44e729"
    procedure_api_token: str = "dev-procedure-token"
    lecture_api_token: str = "dev-lecture-token"
    demo_session_secret: str = "local-demo-session-secret"
    demo_session_ttl_seconds: int = Field(default=43_200, ge=300, le=604_800)
    public_demo_enabled: bool = True
    lecture_visual_max_image_bytes: int = 2_000_000
    lecture_qa_retrieval_limit: int = 5
    lecture_qa_citation_limit: int = Field(default=2, ge=1, le=5)
    # Backward compatibility only: classifier path is currently disabled in lecture QA runtime.
    lecture_qa_classifier_model: str = ""
    # Backward compatibility only: classifier path is currently disabled in lecture QA runtime.
    lecture_qa_classifier_confidence_threshold: float = Field(
        default=0.65,
        ge=0.0,
        le=1.0,
    )
    lecture_qa_repair_mode: Literal["always", "conditional", "off"] = "conditional"
    lecture_qa_answer_max_tokens_fact: int = Field(default=220, ge=32, le=1_024)
    lecture_qa_answer_max_tokens_explanation: int = Field(
        default=420,
        ge=64,
        le=1_024,
    )
    lecture_qa_verify_max_tokens: int = Field(default=220, ge=32, le=1_024)
    lecture_qa_answer_max_retries: int = Field(default=1, ge=0, le=8)
    lecture_qa_answer_retry_delay_seconds: float = Field(default=1.0, ge=0.0, le=10.0)
    lecture_qa_answer_min_request_interval_seconds: float = Field(
        default=0.35,
        ge=0.0,
        le=5.0,
    )
    lecture_live_asr_review_enabled: bool = False
    lecture_live_translation_enabled: bool = False
    lecture_live_summary_enabled: bool = False
    lecture_live_keyterms_enabled: bool = False
    lecture_qa_enabled: bool = False
    lecture_idle_autostop_seconds: int = Field(default=120, ge=30, le=600)
    lecture_summary_rebuild_max_windows: int = Field(
        default=1_200,
        ge=1,
        le=10_000,
    )
    azure_openai_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "AZURE_OPENAI_ENABLED",
            "AZURE_OPENAI_ENABLE",
        ),
    )
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_account_name: str = ""
    azure_openai_model: str = "gpt-5-mini"
    lecture_qa_verifier_model: str = "gpt-5-nano"
    lecture_qa_repair_model: str = "gpt-5-mini"
    azure_openai_api_version: str = "2024-05-01-preview"
    lecture_qa_verify_timeout_seconds: int = Field(default=15, ge=1, le=60)
    lecture_qa_repair_timeout_seconds: int = Field(default=20, ge=1, le=60)
    azure_openai_keyterms_model: str = "gpt-5-nano"
    azure_openai_judge_model: str = "gpt-5-nano"
    asr_hallucination_obvious_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    asr_audit_retry_max: int = Field(default=1, ge=0, le=2)
    asr_judge_timeout_seconds: int = Field(default=20, ge=1, le=60)
    azure_speech_key: str = ""
    azure_speech_region: str = ""
    azure_speech_recognition_locale: str = "ja-JP"
    azure_speech_tts_locale: str = "ja-JP"
    azure_speech_tts_voice: str = "ja-JP-NanamiNeural"
    azure_speech_token_expires_in_sec: int = Field(default=540, ge=1, le=600)
    azure_speech_sts_timeout_seconds: int = Field(default=5, ge=1, le=30)
    azure_vision_enabled: bool = False
    azure_vision_key: str = ""
    azure_vision_endpoint: str = ""
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
    public_demo_rate_limit_bootstrap_per_minute: int = Field(
        default=10,
        ge=1,
        le=600,
    )
    public_demo_rate_limit_lecture_write_per_minute: int = Field(
        default=240,
        ge=1,
        le=2_000,
    )
    public_demo_rate_limit_lecture_read_per_minute: int = Field(
        default=120,
        ge=1,
        le=2_000,
    )
    public_demo_rate_limit_qa_per_minute: int = Field(
        default=30,
        ge=1,
        le=600,
    )
    public_demo_rate_limit_procedure_per_minute: int = Field(
        default=20,
        ge=1,
        le=600,
    )
    public_demo_rate_limit_settings_per_minute: int = Field(
        default=60,
        ge=1,
        le=600,
    )
    weave: WeaveSettings = Field(default_factory=WeaveSettings)

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

    @field_validator("debug", mode="before")
    @classmethod
    def validate_debug_flag(cls, value: object) -> object:
        """Treat common non-boolean release labels as disabled debug."""
        if isinstance(value, str) and value.strip().lower() == "release":
            return False
        return value

    model_config = {
        "env_file": (".env", ".env.azure.generated"),
        "extra": "ignore",
    }


settings = Settings()
