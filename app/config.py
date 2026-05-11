from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    catalog_path: Path = Field(
        default=Path("Data/shl_product_catalog.json"),
        alias="CATALOG_PATH",
    )
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    groq_model: str = Field(default="openai/gpt-oss-120b", alias="GROQ_MODEL")
    groq_fallback_model: str = Field(
        default="openai/gpt-oss-20b",
        alias="GROQ_FALLBACK_MODEL",
    )
    groq_fast_model: str = Field(
        default="openai/gpt-oss-20b",
        alias="GROQ_FAST_MODEL",
    )
    chat_timeout_seconds: int = Field(default=25, alias="CHAT_TIMEOUT_SECONDS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
