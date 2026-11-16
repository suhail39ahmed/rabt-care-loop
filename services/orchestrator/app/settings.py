"""Application settings from environment."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    fhir_base_url: str = "http://localhost:8080/fhir"
    fhir_mode: str = "memory"  # memory | hapi
    database_url: str = "sqlite+aiosqlite:///./data/rabt.db"
    channel: str = "console"
    # Global kill switch — when false, every AI path stays on templates (#105).
    ai_enabled: bool = False
    llm_provider: str = "off"  # off | openai_compatible | azure
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_model: str = ""
    content_safety_endpoint: str = ""
    cs_max_severity: int = 2
    otel_service_name: str = "rabt-orchestrator"
    guest_mode: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    demo_seed: int = 42

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_enabled(self) -> bool:
        if not self.ai_enabled:
            return False
        provider = (self.llm_provider or "off").lower()
        if provider == "off":
            return bool(self.azure_openai_endpoint and self.azure_openai_model)
        model = self.llm_model or self.azure_openai_model
        base = self.llm_base_url or self.azure_openai_endpoint
        return bool(model and base)


@lru_cache
def get_settings() -> Settings:
    return Settings()
