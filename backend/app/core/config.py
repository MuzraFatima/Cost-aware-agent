from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, List

class Settings(BaseSettings):
    # API Configurations
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Cost-Aware Agent Router"

    # CORS Origins
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # Database — pydantic-settings reads DATABASE_URL from env / .env automatically
    DATABASE_URL: str = "sqlite:///./caar.db"

    # API Keys — populated from environment variables or .env file.
    # Placeholder values signal mock/sandbox mode (see is_mock_mode below).
    OPENAI_API_KEY: str = "mock-openai-key"
    ANTHROPIC_API_KEY: str = "mock-anthropic-key"
    GEMINI_API_KEY: str = "mock-gemini-key"

    # Model per tier — overridable via env / .env
    TIER_1_MODEL: str = "gpt-4o-mini"
    TIER_2_MODEL: str = "gpt-4o-mini"
    TIER_3_MODEL: str = "gpt-4o"
    TIER_4_MODEL: str = "gpt-4o"

    # Default confidence thresholds per domain
    DEFAULT_THRESHOLDS: Dict[str, float] = {
        "coding": 0.85,
        "math": 0.85,
        "general": 0.65,
        "creative": 0.50,
    }

    # RAG Vector Store Settings
    CHROMA_DB_DIR: str = "./chroma_db"

    @property
    def is_mock_mode(self) -> bool:
        """
        Returns True when no real provider key has been configured.
        The system falls back to deterministic mock responses in this mode.
        Agents should use this instead of hard-coding key string comparisons.
        """
        no_openai    = self.OPENAI_API_KEY    in ("", "mock-openai-key")
        no_anthropic = self.ANTHROPIC_API_KEY in ("", "mock-anthropic-key")
        no_gemini    = self.GEMINI_API_KEY    in ("", "mock-gemini-key")
        return no_openai and no_anthropic and no_gemini

    model_config = SettingsConfigDict(
        # Load a .env file from the project root when present.
        # Priority: constructor args > env vars > .env file > field defaults.
        env_file=".env",
        env_file_encoding="utf-8",
        # Silently ignore any extra keys present in the .env file.
        extra="ignore",
        case_sensitive=True,
    )

settings = Settings()

