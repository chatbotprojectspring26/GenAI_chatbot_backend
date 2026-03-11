from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow",
    )

    # Core app
    app_name: str = "Research GenAI Chatbot Backend"
    app_env: str = "development"

    # ── MongoDB ──────────────────────────────────────────────────────────────
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "chatbot_research"

    # ── OpenAI LLM ───────────────────────────────────────────────────────────
    openai_api_key: str  # Required — set OPENAI_API_KEY in .env or Railway Variables
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.3
    openai_max_tokens: int = 512

    # ── Experiments ──────────────────────────────────────────────────────────
    default_experiment_id: Optional[str] = None

    # ── Memory window (turns to include in LLM context) ──────────────────────
    memory_window: int = 20

    # ── Qualtrics / Prolific redirects ───────────────────────────────────────
    qualtrics_post_base_url: Optional[str] = None

    # ── CORS / frontend ──────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"


@lru_cache()
def get_settings() -> Settings:
    return Settings()