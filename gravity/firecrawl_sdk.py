from __future__ import annotations
import os
from pydantic import BaseModel, Field
from firecrawl import Firecrawl

FC_KEY = os.getenv("FIRECRAWL_API_KEY")
if not FC_KEY:
    raise RuntimeError("FIRECRAWL_API_KEY env var is required")

fc = Firecrawl(api_key=FC_KEY)

class SocialJSON(BaseModel):
    platform: str | None = None
    handle: str | None = None
    display_name: str | None = None
    verified: bool | None = None
    follower_count: int | None = None
    following_count: int | None = None
    posts_count: int | None = None
    bio_text: str | None = None
    external_links: list[str] = Field(default_factory=list)

def scrape_social_json(url: str, max_age_ms: int = 600000) -> dict:
    result = fc.scrape(
        url=url,
        formats=[{"type": "json", "schema": SocialJSON.model_json_schema()}],
        only_main_content=False,
        timeout=120000,
        maxAge=max_age_ms,
        location={"country": "US", "languages": ["en"]},
    )
    return result
