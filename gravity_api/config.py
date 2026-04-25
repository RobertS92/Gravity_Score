"""Environment-backed settings for the Gravity API."""

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional


@dataclass(frozen=True)
class Settings:
    pg_dsn: str
    environment: str
    frontend_url: str
    anthropic_api_key: str | None
    anthropic_model: str
    cors_origins: str
    cors_origin_regex: str | None
    jwt_secret: str | None
    jwt_algorithm: str
    allow_query_user_id: bool
    ml_service_url: str | None
    ml_api_key: str | None
    internal_api_key: str | None
    scrapers_service_url: Optional[str]
    scrapers_service_api_key: Optional[str]
    redis_url: Optional[str]
    stripe_webhook_secret: Optional[str]
    stripe_secret_key: Optional[str]

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
            "http://localhost:5173,http://localhost:3000,"
            "https://www.gravityscore.ai,https://gravityscore.ai,"
            "https://gravityscore-production.up.railway.app,"
            "https://gravity-terminal-production.up.railway.app",
        ),
        # Default regex lets any *.up.railway.app subdomain through so Railway
        # preview deployments work without re-configuring CORS. Override with
        # CORS_ORIGIN_REGEX="" to disable, or a stricter pattern if needed.
        cors_origin_regex=(
            os.environ.get(
                "CORS_ORIGIN_REGEX",
                r"^https://[A-Za-z0-9._-]+\.up\.railway\.app$",
            ).strip()
            or None
        ),
        jwt_secret=os.environ.get("JWT_SECRET") or os.environ.get("GRAVITY_JWT_SECRET"),
        jwt_algorithm=os.environ.get("JWT_ALGORITHM", "HS256"),
        # Default OFF in production: when JWT is configured, the only way to
        # identify a caller is the bearer token. Set to "1" only for local dev
        # against a backend without auth.
        allow_query_user_id=os.environ.get("GRAVITY_ALLOW_QUERY_USER_ID", "0").lower()
        in ("1", "true", "yes"),
        ml_service_url=(
            os.environ.get("ML_SERVICE_URL") or os.environ.get("ML_API_URL") or ""
        ).rstrip("/")
        or None,
        ml_api_key=os.environ.get("ML_API_KEY") or os.environ.get("ML_SERVICE_API_KEY"),
        internal_api_key=os.environ.get("GRAVITY_INTERNAL_API_KEY"),
        scrapers_service_url=(
            (os.environ.get("SCRAPERS_SERVICE_URL") or "").strip().rstrip("/") or None
        ),
        scrapers_service_api_key=(
            (os.environ.get("SCRAPERS_SERVICE_API_KEY") or "").strip() or None
        ),
        redis_url=(os.environ.get("REDIS_URL") or "").strip() or None,
        stripe_webhook_secret=(os.environ.get("STRIPE_WEBHOOK_SECRET") or "").strip()
        or None,
        stripe_secret_key=(os.environ.get("STRIPE_SECRET_KEY") or "").strip() or None,
    )
