"""Environment-backed settings for the Gravity API."""

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import List


@dataclass(frozen=True)
class Settings:
    pg_dsn: str
    environment: str
    frontend_url: str
    anthropic_api_key: str | None
    anthropic_model: str
    cors_origins: str

    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings(
        pg_dsn=os.environ.get("PG_DSN", "postgresql://localhost:5432/gravity"),
        environment=os.environ.get("ENVIRONMENT", "development"),
        frontend_url=os.environ.get("FRONTEND_URL", "http://localhost:5173"),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        anthropic_model=os.environ.get(
            "ANTHROPIC_MODEL", "claude-sonnet-4-20250514"
        ),
        cors_origins=os.environ.get(
            "CORS_ORIGINS",
            "http://localhost:5173,https://gravity.yourdomain.com",
        ),
    )
