import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, Any, List

class Settings(BaseSettings):
    # API Configurations
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Cost-Aware Agent Router"
    
    # CORS Origins
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./caar.db")
    
    # API Keys (Loaded from environment)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "mock-openai-key")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "mock-anthropic-key")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "mock-gemini-key")
    
    # Model Configurations per Tier
    TIER_1_MODEL: str = os.getenv("TIER_1_MODEL", "gpt-4o-mini")
    TIER_2_MODEL: str = os.getenv("TIER_2_MODEL", "gpt-4o-mini")
    TIER_3_MODEL: str = os.getenv("TIER_3_MODEL", "gpt-4o")
    TIER_4_MODEL: str = os.getenv("TIER_4_MODEL", "gpt-4o")
    
    # Default Confidence Thresholds per Domain
    DEFAULT_THRESHOLDS: Dict[str, float] = {
        "coding": 0.85,
        "math": 0.85,
        "general": 0.65,
        "creative": 0.50
    }
    
    # RAG Vector Store Settings
    CHROMA_DB_DIR: str = "./chroma_db"
    
    model_config = SettingsConfigDict(case_sensitive=True)

settings = Settings()
