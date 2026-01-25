from __future__ import annotations
import os, sys, csv, json, time
import psycopg
from gravity.firecrawl_sdk import scrape_social_json

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
