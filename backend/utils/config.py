from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import List
import os
from pathlib import Path
from dotenv import load_dotenv

# Always load .env from the backend/ folder regardless of working directory
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"

# Load explicitly so env vars are set before pydantic reads them
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE, override=True)


class Settings(BaseSettings):
    # App
    app_env: str = "production"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_secret_key: str = "change_this_secret"

    # Smartsheet
    smartsheet_api_token: str = Field(..., env="SMARTSHEET_API_TOKEN")
    smartsheet_base_url: str = "https://api.smartsheet.com/2.0"
    smartsheet_max_rows: int = 5000

    # Anthropic
    anthropic_api_key: str = Field(..., env="ANTHROPIC_API_KEY")
    claude_model: str = "claude-sonnet-4-5"
    claude_max_tokens: int = 16000

    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_enabled: bool = False

    # Rate limiting
    rate_limit_per_minute: int = 30

    # Supabase
    supabase_url: str = Field(default="", env="SUPABASE_URL")
    supabase_key: str = Field(default="", env="SUPABASE_KEY")

    # JWT
    jwt_secret: str = Field(default="change_this_jwt_secret_in_production", env="JWT_SECRET")

    # CORS
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        env="CORS_ORIGINS"
    )

    # Logging
    log_level: str = "INFO"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    class Config:
        env_file = str(_ENV_FILE)
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()