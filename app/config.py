from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl
from typing import List, Optional, Union


class Settings(BaseSettings):
    # Tell pydantic-settings to load from .env in this directory
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow"  # Allow extra fields like cors_origins
    )

    # Core app
    app_name: str = "Research GenAI Chatbot Backend"
    app_env: str = "development"

    # Database
    database_url: str = "sqlite:///./dev.db"

    # LLM / OpenAI / LLAMA
    openai_api_key: str = "sk-dummy-key-for-local-dev"
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.3
    openai_max_tokens: int = 512
    
    # LLAMA API (university VPN)
    llama_api_key: Optional[str] = None
    llama_api_url: Optional[str] = None
    llama_model: str = "llama-3.1-8b"

    # Experiments
    default_experiment_id: str = "default-experiment"

    # Qualtrics / Prolific redirects (templates)
    qualtrics_post_base_url: Optional[str] = None

    # CORS / frontend - simple string for comma-separated origins
    cors_origins: Optional[str] = "http://localhost:3000,http://127.0.0.1:3000"


@lru_cache()
def get_settings() -> Settings:
    return Settings()