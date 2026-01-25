# pip install firecrawl-py python-dotenv
import os, re, json, csv, time
from typing import List, Dict, Any, Optional
from firecrawl import Firecrawl
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("FIRECRAWL_API_KEY", "fc-YOUR-API-KEY")
if not API_KEY.startswith("fc-"):
    raise ValueError("Set FIRECRAWL_API_KEY")

app = Firecrawl(api_key=API_KEY)

INDEX_URL = "https://www.espn.com/nfl/players"

# Structured extractor for roster pages
JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "team": {"type": "string"},
        "players": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "position": {"type": "string"},
                    "jersey_number": {"type": ["string","number","null"]}
                },
                "required": ["name"]
            }
        }
    },
    "required": ["team","players"]
}

JSON_PROMPT = (
    "Extract the current NFL roster shown on this ESPN team roster page. "
    "Return JSON with: team (string) and players (array of {name, position, jersey_number}). "
    "Use standard short position codes if visible (QB, WR, CB, etc.), else 'UNK'. "
    "If jersey number not shown, null."
)

def fetch_index_raw() -> Dict[str, Any]:
    """
    Fetch index page with retry logic and timeout handling.
    Returns empty dict if it fails - we have fallback URLs.
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"Attempting to fetch index page (attempt {attempt + 1}/{max_retries})...")
            result = app.scrape(
                url=INDEX_URL,
                formats=["rawHtml", "links"],
                max_age=0,
                location={"country":"US", "languages":["en"]},
                timeout=60000  # Reduced timeout to 60 seconds
            )
            # Normalize to dict
            if hasattr(result, "model_dump"):
                return result.model_dump()
            elif hasattr(result, "dict"):
                return result.dict()
            return result if isinstance(result, dict) else {}
        except Exception as e:
            error_msg = str(e).lower()
            if "503" in error_msg or "timeout" in error_msg:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5  # 5s, 10s, 15s
                    print(f"  ⚠ Timeout/503 error, retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"  ⚠ Index page scrape failed after {max_retries} attempts: {e}")
                    print(f"  → Will use fallback team URLs")
                    return {}
            else:
                print(f"  ⚠ Error fetching index: {e}")
                return {}
    return {}

def parse_team_urls_from_links(links: List[str]) -> List[str]:
    urls = set()
    if not links: return []
    for href in links:
        if isinstance(href,str) and "/nfl/team/roster/_/name/" in href:
            # normalize to a canonical URL form
            base = href.split("#")[0].split("?")[0].rstrip("/")
            urls.add(base + "/")
    return sorted(urls)

def parse_team_urls_from_rawhtml(raw_html: str) -> List[str]:
    if not raw_html: return []
    # 1) direct anchor scan
    anchors = re.findall(r'href="(https://www\.espn\.com/nfl/team/roster/_/name/[^"]+)"', raw_html)
    if anchors:
        return sorted({a.split("#")[0].split("?")[0].rstrip("/") + "/" for a in anchors})
    # 2) fallback: hydrate blob window['__espnfitt__']=<json>;
    #    Not always present on this page, but keep it as a backstop.
    try:
        # split on the assignment; the blob typically ends at the first semicolon after it
        prefix = "window['__espnfitt__']="  # sometimes window.__espn on other pages
        if prefix in raw_html:
            blob = raw_html.split(prefix,1)[1]
            blob = blob.split("</script>",1)[0]
            # trim potential trailing semicolon/newline
            blob = blob.rstrip(";\n\r ")
            data = json.loads(blob)
            # Walk for team roster hrefs if present (structure can vary)
            text = json.dumps(data)
            anchors2 = re.findall(r'https://www\.espn\.com/nfl/team/roster/_/name/[^"\\]+', text)
            if anchors2:
                return sorted({a.rstrip("/")+ "/" for a in anchors2})
    except Exception:
        pass
    return []

def discover_team_roster_urls() -> List[str]:
    """
    Discover team roster URLs from index page, with fallback to hardcoded URLs.
    """
    # Hardcoded fallback URLs (always available)
    FALLBACK_URLS = {
        "https://www.espn.com/nfl/team/roster/_/name/ari/",
        "https://www.espn.com/nfl/team/roster/_/name/atl/",
        "https://www.espn.com/nfl/team/roster/_/name/bal/",
        "https://www.espn.com/nfl/team/roster/_/name/buf/",
        "https://www.espn.com/nfl/team/roster/_/name/car/",
        "https://www.espn.com/nfl/team/roster/_/name/chi/",
        "https://www.espn.com/nfl/team/roster/_/name/cin/",
        "https://www.espn.com/nfl/team/roster/_/name/cle/",
        "https://www.espn.com/nfl/team/roster/_/name/dal/",
        "https://www.espn.com/nfl/team/roster/_/name/den/",
        "https://www.espn.com/nfl/team/roster/_/name/det/",
        "https://www.espn.com/nfl/team/roster/_/name/gb/",
        "https://www.espn.com/nfl/team/roster/_/name/hou/",
        "https://www.espn.com/nfl/team/roster/_/name/ind/",
        "https://www.espn.com/nfl/team/roster/_/name/jax/",
        "https://www.espn.com/nfl/team/roster/_/name/kc/",
        "https://www.espn.com/nfl/team/roster/_/name/lv/",
        "https://www.espn.com/nfl/team/roster/_/name/lac/",
        "https://www.espn.com/nfl/team/roster/_/name/lar/",
        "https://www.espn.com/nfl/team/roster/_/name/mia/",
        "https://www.espn.com/nfl/team/roster/_/name/min/",
        "https://www.espn.com/nfl/team/roster/_/name/ne/",
        "https://www.espn.com/nfl/team/roster/_/name/no/",
        "https://www.espn.com/nfl/team/roster/_/name/nyg/",
        "https://www.espn.com/nfl/team/roster/_/name/nyj/",
        "https://www.espn.com/nfl/team/roster/_/name/phi/",
        "https://www.espn.com/nfl/team/roster/_/name/pit/",
        "https://www.espn.com/nfl/team/roster/_/name/sf/",
        "https://www.espn.com/nfl/team/roster/_/name/sea/",
        "https://www.espn.com/nfl/team/roster/_/name/tb/",
        "https://www.espn.com/nfl/team/roster/_/name/ten/",
        "https://www.espn.com/nfl/team/roster/_/name/wsh/",
    }
    
    doc = fetch_index_raw()
    
    # If index fetch failed, use fallback immediately
    if not doc:
        print("Using fallback team URLs (index page unavailable)")
        return sorted(FALLBACK_URLS)
    
    # Handle both Document object and dict
    if hasattr(doc, "links"):
        links = doc.links if doc.links else []
        raw_html = getattr(doc, "rawHtml", None) or getattr(doc, "raw_html", None) or ""
    else:
        links = doc.get("links") or []
        raw_html = doc.get("rawHtml") or doc.get("raw_html") or ""
    
    urls = parse_team_urls_from_links(links)
    if len(urls) < 28:
        urls = sorted(set(urls) | set(parse_team_urls_from_rawhtml(raw_html)))
    if len(urls) < 28:
        # ultra-safe fallback: known list if ESPN changes markup
        urls = sorted(set(urls) | FALLBACK_URLS)
    return urls

def team_name_from_url(url: str) -> str:
    # last segment after /name/<abbr>/
    abbr = url.rstrip("/").split("/name/")[-1]
    mapping = {
        "ari":"Arizona Cardinals","atl":"Atlanta Falcons","bal":"Baltimore Ravens","buf":"Buffalo Bills",
        "car":"Carolina Panthers","chi":"Chicago Bears","cin":"Cincinnati Bengals","cle":"Cleveland Browns",
        "dal":"Dallas Cowboys","den":"Denver Broncos","det":"Detroit Lions","gb":"Green Bay Packers",
        "hou":"Houston Texans","ind":"Indianapolis Colts","jax":"Jacksonville Jaguars","kc":"Kansas City Chiefs",
        "lv":"Las Vegas Raiders","lac":"Los Angeles Chargers","lar":"Los Angeles Rams","mia":"Miami Dolphins",
        "min":"Minnesota Vikings","ne":"New England Patriots","no":"New Orleans Saints","nyg":"New York Giants",
        "nyj":"New York Jets","phi":"Philadelphia Eagles","pit":"Pittsburgh Steelers","sf":"San Francisco 49ers",
        "sea":"Seattle Seahawks","tb":"Tampa Bay Buccaneers","ten":"Tennessee Titans","wsh":"Washington Commanders"
    }
    return mapping.get(abbr, abbr.upper())

def scrape_rosters(urls: List[str]) -> List[Dict[str,Any]]:
    """
    Scrape rosters with batch processing, breaking into smaller chunks to avoid timeouts.
    Uses optimized batch size from environment or default.
    """
    # Break into batches - use larger batch size for better performance
    batch_size = int(os.getenv("BATCH_SIZE", "20"))  # Increased from 10 to 20
    all_data = []
    
    for i in range(0, len(urls), batch_size):
        batch_urls = urls[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(len(urls)-1)//batch_size + 1} ({len(batch_urls)} URLs)...")
        
        try:
            job = app.batch_scrape(
                batch_urls,
                formats=[
                    {"type":"json","schema":JSON_SCHEMA,"prompt":JSON_PROMPT},
                    "markdown"
                ],
                max_age=0,
                location={"country":"US","languages":["en"]},
                poll_interval=2,  # Reduced from 3 to 2 for faster polling
                wait_timeout=300  # 5 minutes per batch
            )
            # Handle both Document object and dict
            if hasattr(job, "data"):
                batch_data = job.data if job.data else []
            else:
                batch_data = job.get("data", [])
            all_data.extend(batch_data)
            print(f"✓ Batch {i//batch_size + 1} completed ({len(batch_data)} results)")
            time.sleep(2)  # Brief pause between batches
        except Exception as e:
            print(f"⚠ Batch {i//batch_size + 1} failed: {e}")
            print(f"  Falling back to sequential scraping for this batch...")
            # Fallback: scrape sequentially
            for url in batch_urls:
                try:
                    result = app.scrape(
                        url=url,
                        formats=[
                            {"type":"json","schema":JSON_SCHEMA,"prompt":JSON_PROMPT},
                            "markdown"
                        ],
                        max_age=0,
                        location={"country":"US","languages":["en"]},
                        timeout=30000
                    )
                    # Normalize to dict format
                    if hasattr(result, "model_dump"):
                        result = result.model_dump()
                    elif hasattr(result, "dict"):
                        result = result.dict()
                    elif not isinstance(result, dict):
                        # Try to convert Pydantic model to dict
                        result = dict(result) if hasattr(result, "__dict__") else {}
                    all_data.append(result)
                    time.sleep(1)  # Rate limiting
                except Exception as seq_error:
                    print(f"  ⚠ Failed to scrape {url}: {seq_error}")
                    continue
    
    data = all_data
    out: List[Dict[str,Any]] = []

    # very lenient markdown fallback
    name_pat = re.compile(r"^[A-Z][a-zA-Z\.'\-]+(?:\s[A-Z][a-zA-Z\.'\-]+)+(?:\s(Jr\.|Sr\.|III|II))?$")
    pos_pat = re.compile(r"\b(QB|RB|WR|TE|OL|C|G|T|DL|DE|DT|LB|ILB|OLB|DB|CB|S|FS|SS|K|P|LS|NT|EDGE|FB|OT|OG)\b")

    for i, item in enumerate(data):
        # Normalize item to dict if it's a Document object
        if not isinstance(item, dict):
            if hasattr(item, "model_dump"):
                item = item.model_dump()
            elif hasattr(item, "dict"):
                item = item.dict()
            else:
                item = {}
        
        # Get URL for this item (may need to track URLs separately)
        url = item.get("url") or (urls[i] if i < len(urls) else "")
        team = team_name_from_url(url)
        
        # Try to get JSON extraction result
        js = item.get("json")
        if not js and hasattr(item, "extract"):
            extract = item.get("extract") or {}
            js = extract.get("data") if isinstance(extract, dict) else None
        
        if isinstance(js, dict) and js.get("players"):
            tname = js.get("team") or team
            for p in js["players"]:
                nm = (p.get("name") or "").strip()
                if not nm: continue
                pos = (p.get("position") or "UNK").strip()
                out.append({"name": nm, "team": tname, "position": pos, "jersey_number": p.get("jersey_number")})
            continue

        md = item.get("markdown") or ""
        players = []
        for ln in (ln.strip() for ln in md.splitlines() if ln.strip()):
            cells = [c.strip() for c in re.split(r"\s*\|\s*", ln) if c.strip()]
            text = " ".join(cells) if len(cells) >= 2 else ln
            mname = name_pat.search(text)
            if not mname: continue
            name = mname.group(0)
            mpos = pos_pat.search(text)
            pos = mpos.group(1) if mpos else "UNK"
            mnum = re.search(r"\b(\d{1,2})\b", text)
            jersey = mnum.group(1) if mnum else None
            players.append((name,pos,jersey))
        # de-dup
        seen = set()
        for nm,pos,jn in players:
            if (nm,team) in seen: continue
            seen.add((nm,team))
            out.append({"name": nm, "team": team, "position": pos, "jersey_number": jn})

        time.sleep(0.05)

    # global de-dup (name+team)
    uniq = []
    seen = set()
    for r in out:
        k = (r["name"], r["team"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    return uniq

def export(players: List[Dict[str,Any]]):
    with open("nfl_players_2025.json","w",encoding="utf-8") as f:
        json.dump(players,f,indent=2,ensure_ascii=False)
    with open("nfl_players_2025.csv","w",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f,fieldnames=["name","team","position","jersey_number"])
        w.writeheader(); w.writerows(players)
    # names-per-team text
    per = {}
    for p in players: per.setdefault(p["team"], []).append(p["name"])
    with open("nfl_player_names_by_team_2025.txt","w",encoding="utf-8") as f:
        for team in sorted(per):
            f.write(team+"\n")
            for nm in sorted(set(per[team])):
                f.write(f"- {nm}\n")
            f.write("\n")
    print("✓ Wrote nfl_players_2025.json / nfl_players_2025.csv / nfl_player_names_by_team_2025.txt")

def main():
    print("Discovering roster URLs from ESPN Players index (via source/links)…")
    roster_urls = discover_team_roster_urls()
    print(f"Found {len(roster_urls)} roster pages")
    players = scrape_rosters(roster_urls)
    print(f"Collected {len(players)} player rows")
    export(players)

if __name__ == "__main__":
    main()
