from __future__ import annotations

import csv
import json
import os
import re
import sys
import time

import psycopg
import requests

FIRECRAWL_V2 = "https://api.firecrawl.dev/v2"


def scrape_social_json(url: str) -> dict:
    """Firecrawl v2 markdown scrape; map rough follower counts into legacy JSON shape."""
    key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if not key:
        raise RuntimeError("FIRECRAWL_API_KEY is required")
    resp = requests.post(
        f"{FIRECRAWL_V2}/scrape",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"url": url, "formats": [{"type": "markdown"}], "onlyMainContent": True},
        timeout=120,
    )
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        raise RuntimeError(body.get("error", "scrape_failed"))
    md = (body.get("data") or {}).get("markdown") or ""
    follower = None
    for pat in (r"([\d,.]+)\s+Followers", r"([\d,.]+)\s+followers", r"\"follower_count\":\s*(\d+)"):
        m = re.search(pat, md)
        if m:
            try:
                follower = int(m.group(1).replace(",", "").replace(".", "")[:15])
                break
            except ValueError:
                continue
    return {
        "data": {
            "json": {
                "platform": None,
                "handle": None,
                "follower_count": follower,
                "bio_text": md[:2000] if md else None,
                "external_links": [],
            }
        }
    }

PG_DSN = os.getenv("PG_DSN", f"postgresql://{os.getenv('USER','postgres')}@localhost:5432/gravity")

USAGE = "Usage: python scripts/scrape_social_firecrawl.py urls.csv"

def upsert_snapshot(cur, athlete_id, platform, handle, profile_url, payload):
    ext_links = payload.get("external_links") or []
    cur.execute("""
        INSERT INTO social_snapshots
          (athlete_id, platform, handle, profile_url, follower_count, following_count, posts_count, verified, bio, external_links, scraped_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
        ON CONFLICT DO NOTHING;
    """, (
        athlete_id,
        platform,
        handle,
        profile_url,
        payload.get("follower_count"),
        payload.get("following_count"),
        payload.get("posts_count"),
        payload.get("verified"),
        payload.get("bio_text"),
        json.dumps(ext_links),
    ))

def main(csv_path: str):
    if not os.path.exists(csv_path):
        print(USAGE); sys.exit(2)
    with psycopg.connect(PG_DSN, autocommit=True) as conn, conn.cursor() as cur, open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            athlete_id = row["athlete_id"].strip()
            platform = row["platform"].strip().lower()
            url = row["profile_url"].strip()
            try:
                result = scrape_social_json(url)
                data = result.get("data", {})
                js = data.get("json") or {}
                payload = {
                    "platform": js.get("platform") or platform,
                    "handle": js.get("handle"),
                    "display_name": js.get("display_name"),
                    "verified": js.get("verified"),
                    "follower_count": js.get("follower_count"),
                    "following_count": js.get("following_count"),
                    "posts_count": js.get("posts_count"),
                    "bio_text": js.get("bio_text"),
                    "external_links": js.get("external_links") or [],
                }
                upsert_snapshot(cur, athlete_id, platform, payload["handle"], url, payload)
                print(f"OK {athlete_id} {platform} {url}")
            except Exception as e:
                print(f"ERR {athlete_id} {platform} {url} -> {e}")
                time.sleep(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(USAGE); sys.exit(1)
    main(sys.argv[1])
