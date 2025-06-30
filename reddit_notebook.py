#!/usr/bin/env python3
import os
import sys
import json
import re
import time
import datetime
import argparse
import requests
import praw
from datetime import timezone
from prawcore import ResponseException, Redirect, TooManyRequests

# Alpha Vantage for stocks
from alpha_vantage.timeseries import TimeSeries

# Google APIs
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# ── GoldAPI endpoints ───────────────────────────────────────────────
GOLDAPI_URLS = {
    "Gold":   "https://www.goldapi.io/api/XAU/USD",
    "Silver": "https://www.goldapi.io/api/XAG/USD",
}

# ── Load configuration ───────────────────────────────────────────────
with open("config.json", "r", encoding="utf-8") as f:
    cfg = json.load(f)

# ── Persistent author cache ─────────────────────────────────────────
CACHE_PATH = "author_cache.json"
if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH, "r", encoding="utf-8") as cf:
        author_cache = json.load(cf)
else:
    author_cache = {}

# ── Read thresholds & defaults ───────────────────────────────────────
comment_age_thresh = cfg.get("comment_age_threshold_days", 0)
default_subs       = cfg.get("subreddits", [])
default_hours      = cfg.get("default", {}).get("hours", 24)
default_topn       = cfg.get("default", {}).get("top_posts", 0)
default_comments   = cfg.get("output", {}).get("include_comments", False)

# ── Stocks config ────────────────────────────────────────────────────
stocks_cfg    = cfg.get("stocks", {})
stocks_enabled = stocks_cfg.get("enabled", False)
stock_symbols  = stocks_cfg.get("symbols", [])
av_cfg         = stocks_cfg.get("alpha_vantage", {})
av_api_key     = av_cfg.get("api_key", "")

# ── Commodities config ───────────────────────────────────────────────
comms_cfg      = cfg.get("commodities", {})
comms_enabled = comms_cfg.get("enabled", False)
commodity_items = comms_cfg.get("items", [])
goldapi_cfg   = comms_cfg.get("goldapi", {})
goldapi_token = goldapi_cfg.get("access_token", "")

# ── Weather config ──────────────────────────────────────────────────
weather_cfg = cfg.get("weather", {})
weather_enabled = weather_cfg.get("enabled", False)
wa_api_key      = weather_cfg.get("api_key", "")
loc             = weather_cfg.get("location", {})
units           = weather_cfg.get("units", "metric")

# ── CLI args ─────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(
    description="Fetch Reddit posts, market data, weather, and optionally upload to Google Docs."
)
parser.add_argument("-s", "--subreddits", nargs="+",
                    help="Override subreddits in config")
parser.add_argument("-H", "--hours", type=int, default=default_hours,
                    help="Hours to look back")
parser.add_argument("-n", "--topn", type=int, default=default_topn,
                    help="How many top posts (0=all)")
parser.add_argument("-c", "--comments", action="store_true",
                    default=default_comments, help="Include comments & links")
parser.add_argument("--no-drive", dest="drive", action="store_false",
                    help="Disable Google Drive upload")
args = parser.parse_args()

subs = args.subreddits if args.subreddits else default_subs
if not subs:
    print("ERROR: No subreddits specified.", file=sys.stderr)
    sys.exit(1)

# ── Reddit client setup ──────────────────────────────────────────────
rd = cfg["reddit"]
reddit = praw.Reddit(
    client_id=rd["client_id"],
    client_secret=rd["client_secret"],
    user_agent=rd["user_agent"],
    check_for_async=False
)

# ── Google Drive & Docs setup ────────────────────────────────────────
drive_service = docs_service = None
if args.drive and cfg.get("drive", {}).get("enabled", False):
    SCOPES = ["https://www.googleapis.com/auth/drive.file",
              "https://www.googleapis.com/auth/documents"]
    token_path = "token.json"
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                cfg["drive"]["credentials_file"], SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as tok:
            tok.write(creds.to_json())
    drive_service = build("drive", "v3", credentials=creds)
    docs_service  = build("docs", "v1", credentials=creds)

# ── Fetch stock prices via Alpha Vantage ─────────────────────────────
def fetch_stock_prices(symbols):
    if not (stocks_enabled and av_api_key and symbols):
        return {}
    ts = TimeSeries(key=av_api_key, output_format="json")
    out = {}
    for s in symbols:
        try:
            data, _ = ts.get_quote_endpoint(symbol=s)
            out[s]   = float(data.get("05. price", 0.0))
        except Exception:
            out[s]   = None
    return out

# ── Fetch metal prices via GoldAPI ──────────────────────────────────
def fetch_commodity_prices(items):
    if not (comms_enabled and goldapi_token and items):
        return {}
    headers = {"x-access-token": goldapi_token}
    out     = {}
    for name in items:
        url = GOLDAPI_URLS.get(name)
        if not url:
            out[name] = None; continue
        try:
            r = requests.get(url, headers=headers, timeout=5)
            r.raise_for_status()
            out[name] = r.json().get("price")
        except Exception:
            out[name] = None
    return out

# ── Fetch weather via free v2.5 endpoint ────────────────────────────
def fetch_weather(api_key, lat, lon, units="metric"):
    if not (weather_enabled and api_key and lat is not None and lon is not None):
        return {}
    url = (f"https://api.openweathermap.org/data/2.5/weather"
           f"?lat={lat}&lon={lon}&units={units}&appid={api_key}")
    r = requests.get(url, timeout=5)
    r.raise_for_status()
    w = r.json()
    return {
        "summary":  w["weather"][0]["description"].title(),
        "temp":     w["main"]["temp"],
        "humidity": w["main"]["humidity"],
        "wind":     w["wind"].get("speed")
    }

# ── Google Drive folder helpers ──────────────────────────────────────
def ensure_drive_folder(name: str) -> str:
    resp  = drive_service.files().list(
        q=("mimeType='application/vnd.google-apps.folder' "
           f"and name='{name}' and trashed=false"),
        fields="files(id,name)"
    ).execute()
    items = resp.get("files", [])
    if items:
        return items[0]["id"]
    folder = drive_service.files().create(
        body={"name": name, "mimeType": "application/vnd.google-apps.folder"},
        fields="id"
    ).execute()
    return folder["id"]

def ensure_folder_in_parent(parent_id: str, name: str) -> str:
    q     = ("mimeType='application/vnd.google-apps.folder' "
             f"and name='{name}' and '{parent_id}' in parents and trashed=false")
    resp  = drive_service.files().list(q=q, fields="files(id,name)").execute()
    items = resp.get("files", [])
    if items:
        return items[0]["id"]
    meta = {"name": name,
            "mimeType":"application/vnd.google-apps.folder",
            "parents":[parent_id]}
    folder = drive_service.files().create(body=meta, fields="id").execute()
    return folder["id"]

# ── Reddit fetch ─────────────────────────────────────────────────────
def fetch_posts(sr, hrs, topn):
    try:
        sub = reddit.subreddit(sr); _ = sub.display_name
    except (Redirect, ResponseException) as e:
        print(f"ERROR fetching r/{sr}: {e}", file=sys.stderr)
        sys.exit(1)
    cutoff = (datetime.datetime.now(timezone.utc)
              - datetime.timedelta(hours=hrs)).timestamp()
    posts, total = [], 0
    tf_map = {1:"hour",24:"day",168:"week",720:"month",8760:"year"}
    if topn>0 and hrs in tf_map:
        for p in sub.top(time_filter=tf_map[hrs], limit=topn):
            total += 1; posts.append(p)
        return total, posts
    for p in sub.new(limit=None):
        if p.created_utc < cutoff:
            break
        total += 1; posts.append(p)
    if topn>0:
        posts = sorted(posts, key=lambda x: x.score, reverse=True)[:topn]
    return total, posts

# ── Comment extraction with age filter ───────────────────────────────
def extract_comments(subm):
    subm.comments.replace_more(limit=None)
    flat = subm.comments.list()
    pat  = re.compile(r"https?://\S+")
    out  = []
    for c in flat:
        if c.author and hasattr(c.author, "created_utc"):
            age = (datetime.datetime.now(timezone.utc) -
                   datetime.datetime.fromtimestamp(c.author.created_utc,
                                                  tz=timezone.utc)).days
        else:
            age = None
        if age is not None and age < comment_age_thresh:
            continue

        depth = getattr(c, "depth", 0)
        author = c.author.name if c.author else "[deleted]"
        acct_iso = author_cache.get(author, "")
        if author and author not in author_cache:
            try:
                acct = reddit.redditor(author)
                acct_iso = datetime.datetime.fromtimestamp(
                    acct.created_utc, tz=timezone.utc).isoformat()
                author_cache[author] = acct_iso
                time.sleep(0.2)
            except TooManyRequests:
                author_cache[author] = ""
            except:
                author_cache[author] = ""

        text  = c.body.replace("\n", " ")
        links = pat.findall(text)
        out.append((depth, author, acct_iso, text, links))
    return out

# ── Markdown writer ─────────────────────────────────────────────────
def write_markdown(subs, hrs, total_map, posts_map,
                   grab, stocks, metals, weather, out_dir):
    now   = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    fname = f"reddit_digest_{now}.md"
    os.makedirs(out_dir, exist_ok=True)
    path  = os.path.join(out_dir, fname)

    with open(path, "w", encoding="utf-8") as md:
        md.write(f"# Reddit Digest — Last {hrs}h\n\n")

        if weather:
            md.write("## Weather\n")
            md.write(f"- Condition: {weather['summary']}\n")
            md.write(f"- Temp: {weather['temp']}°{'C' if units=='metric' else 'F'}\n")
            md.write(f"- Humidity: {weather['humidity']}%\n")
            md.write(f"- Wind: {weather['wind']} m/s\n\n")

        if stocks:
            md.write("## Stock Prices\n")
            for s, p in stocks.items():
                md.write(f"- {s}: {p}\n")
            md.write("\n")

        if metals:
            md.write("## Commodity Prices\n")
            for m, p in metals.items():
                md.write(f"- {m}: {p}\n")
            md.write("\n")

        for sr in subs:
            total, posts = total_map[sr], posts_map[sr]
            md.write(f"---\n## r/{sr} — {len(posts)} of {total} posts\n\n")
            for i, p in enumerate(posts, 1):
                created = datetime.datetime.fromtimestamp(p.created_utc, tz=timezone.utc)
                md.write(f"### {i}. {p.title}\n")
                md.write(f"- URL: {p.url}\n")
                md.write(f"- Permalink: https://reddit.com{p.permalink}\n")
                md.write(f"- Score: {p.score} | Comments: {p.num_comments} | Created (UTC): {created.isoformat()}\n\n")
                if grab:
                    comments = extract_comments(p)
                    if comments:
                        md.write("#### Comments\n")
                        for idx, (depth, author, acct_iso, body, links) in enumerate(comments, 1):
                            indent = "  " * depth
                            age_str = ""
                            if acct_iso:
                                dt = datetime.datetime.fromisoformat(acct_iso)
                                age_days = (datetime.datetime.now(timezone.utc) - dt).days
                                age_str = f" (age:{age_days}d)"
                            md.write(f"{indent}{idx}. **u/{author}**{age_str}: {body}\n")
                            for l in links:
                                md.write(f"{indent}   - 🔗 {l}\n")
                            md.write("\n")
    return path

def upload_markdown_as_doc(md_path, folder_id):
    text = open(md_path, "r", encoding="utf-8").read()
    doc  = docs_service.documents().create(
        body={"title": os.path.basename(md_path).replace(".md","")}
    ).execute()
    did = doc["documentId"]
    docs_service.documents().batchUpdate(
        documentId=did,
        body={"requests":[{"insertText":{"location":{"index":1},"text":text}}]}
    ).execute()
    drive_service.files().update(
        fileId=did, addParents=folder_id, fields="id,parents"
    ).execute()
    print(f"Created Google Doc: https://docs.google.com/document/d/{did}/edit")

# ── Main ─────────────────────────────────────────────────────────────
def main():
    stock_data     = fetch_stock_prices(stock_symbols)
    commodity_data = fetch_commodity_prices(commodity_items)
    weather_data   = fetch_weather(wa_api_key,
                                   loc.get("lat"),
                                   loc.get("lon"),
                                   units)

    total_map, post_map = {}, {}
    for sr in subs:
        t, p = fetch_posts(sr, args.hours, args.topn)
        total_map[sr] = t
        post_map[sr]  = p

    out_dir = cfg["output"]["local_dir"]
    md_path = write_markdown(subs, args.hours,
                             total_map, post_map,
                             args.comments,
                             stock_data,
                             commodity_data,
                             weather_data,
                             out_dir)
    print(f"Saved markdown to {md_path}")

    with open(CACHE_PATH, "w", encoding="utf-8") as cf:
        json.dump(author_cache, cf)

    if args.drive and cfg.get("drive", {}).get("enabled", False):
        parent_id = ensure_drive_folder(cfg["drive"]["folder_name"])
        today     = datetime.datetime.now().strftime("%Y-%m-%d")
        folder_id = ensure_folder_in_parent(parent_id, today)
        upload_markdown_as_doc(md_path, folder_id)

if __name__ == "__main__":
    main()
