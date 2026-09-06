from functools import lru_cache
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "EQi-30 AI Service"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    API_V1_STR: str = "/api/v1"
    # Internal service-to-service AI API prefix. Django calls this surface;
    # it is never exposed directly to the frontend.
    INTERNAL_API_V1_STR: str = "/internal/ai/v1"
    CORS_ORIGINS: List[str] = ["*"]

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    SERVICE_API_KEY: str = "dev_secret_key_change_in_production"

    # --- AI safety hardening (Phase 14) ---
    # Maximum accepted request body size, in bytes. Defends against
    # oversized-payload abuse: wire schemas cap individual string fields
    # (e.g. ChatRequest.message), but ChatContext's journey/competency/
    # ability/progress blocks are intentionally open Dict[str, Any] with no
    # per-field cap (the backend context contract isn't finalized), so a
    # global body-size ceiling is the only structural bound on total
    # request size. ~2MB comfortably exceeds the legitimate maximum
    # (100 history turns x 8000 chars + message + reasonable context).
    MAX_REQUEST_BODY_BYTES: int = 2_000_000

    # In-memory, per-process request rate limiting for the LLM-calling chat
    # endpoint, protecting against repeated-request abuse and unbounded LLM
    # cost. See app/core/rate_limit.py for the documented single-instance
    # scope/limitation of this control.
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_MAX_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: float = 60.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        return v


@lru_cache()
def get_settings() -> Settings:
    return Settings()
