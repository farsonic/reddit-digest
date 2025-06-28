#!/usr/bin/env python3
import os
import sys
import json
import re
import time
import datetime
import praw
from datetime import timezone
from prawcore import ResponseException, Redirect

# Optional Google APIs imports
try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

# ── Load configuration ────────────────────────────────────────────────
CONFIG_PATH = "config.json"
with open(CONFIG_PATH, "r") as cfg_file:
    cfg = json.load(cfg_file)

# ── Set up Reddit client ─────────────────────────────────────────────
rd = cfg["reddit"]
reddit = praw.Reddit(
    client_id=rd["client_id"],
    client_secret=rd["client_secret"],
    user_agent=rd["user_agent"],
    check_for_async=False
)

# Globals for Google services
drive_service = docs_service = None

def setup_google_clients():
    """
    Initialize Google Drive & Docs clients using Installed-App OAuth.
    Returns (drive_service, docs_service).
    """
    SCOPES = [
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/documents"
    ]
    token_path = "token.json"
    creds = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                cfg["drive"]["credentials_file"], SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())

    drive = build("drive", "v3", credentials=creds)
    docs = build("docs", "v1", credentials=creds)
    return drive, docs


def ensure_drive_folder(name: str, drive_service) -> str:
    """Find or create a folder in My Drive by name; return its ID."""
    resp = drive_service.files().list(
        q=(
            "mimeType='application/vnd.google-apps.folder' "
            f"and name='{name}' and trashed=false"
        ),
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


def fetch_posts(subr: str, hours: int, top_n: int):
    """Return (total_count, list_of_Submission) for posts in last `hours`."""
    try:
        sr = reddit.subreddit(subr)
        _ = sr.display_name
    except Redirect:
        print(f"ERROR: r/{subr} not found", file=sys.stderr); sys.exit(1)
    except ResponseException as e:
        print(f"ERROR: Auth error: {e}", file=sys.stderr); sys.exit(1)

    cutoff_ts = (
        datetime.datetime.now(timezone.utc)
        - datetime.timedelta(hours=hours)
    ).timestamp()

    tf_map = {1:"hour", 24:"day", 168:"week", 720:"month", 8760:"year"}
    posts, total = [], 0

    if top_n > 0 and hours in tf_map:
        for p in sr.top(time_filter=tf_map[hours], limit=top_n):
            total += 1; posts.append(p)
        return total, posts

    for p in sr.new(limit=None):
        if p.created_utc < cutoff_ts:
            break
        total += 1; posts.append(p)

    if top_n > 0:
        posts.sort(key=lambda x: x.score, reverse=True)
        posts = posts[:top_n]

    return total, posts


def extract_comments_and_links(submission):
    """Return [(comment_text, [urls]), …] for top-level comments."""
    submission.comments.replace_more(limit=None)
    pattern = re.compile(r"https?://\S+")
    out = []
    for c in submission.comments:
        text = c.body.replace("\n", " ")
        links = pattern.findall(text)
        out.append((text, links))
    return out


def write_markdown(subr, hours, total, posts, grab_comments, out_dir):
    now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    fname = f"{subr}_{hours}h_top{len(posts)}_{now}.md"
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, fname)

    with open(path, "w", encoding="utf-8") as md:
        md.write(f"# r/{subr} — Top {len(posts)} posts in last {hours}h\n")
        md.write(f"Total posts found: {total}\n\n")
        for i, p in enumerate(posts, 1):
            created = datetime.datetime.fromtimestamp(p.created_utc, tz=timezone.utc)
            md.write(f"## {i}. {p.title}\n")
            md.write(f"- URL: {p.url}\n")
            md.write(f"- Permalink: https://reddit.com{p.permalink}\n")
            md.write(
                f"- Score: {p.score} | Comments: {p.num_comments} | "
                f"Created (UTC): {created.isoformat()}\n\n"
            )
            if grab_comments:
                md.write("### Comments\n")
                for j, (txt, links) in enumerate(extract_comments_and_links(p), 1):
                    md.write(f"{j}. {txt}\n")
                    for link in links:
                        md.write(f"   - Link: {link}\n")
                    md.write("\n")
            time.sleep(0.1)
    return path


def upload_markdown_as_doc(md_path, folder_id, drive_service, docs_service):
    """Convert the markdown into a Google Doc in the given folder."""
    with open(md_path, "r", encoding="utf-8") as f:
        md = f.read()
    doc = docs_service.documents().create(
        body={"title": os.path.basename(md_path).replace(".md","")}
    ).execute()
    doc_id = doc["documentId"]
    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests":[{"insertText": {"location": {"index": 1}, "text": md}}]}
    ).execute()
    drive_service.files().update(
        fileId=doc_id,
        addParents=folder_id,
        fields="id, parents"
    ).execute()
    print(f"Created Google Doc: https://docs.google.com/document/d/{doc_id}/edit")


def main():
    subr = input("Subreddit (e.g. 'worldnews'): ").strip()
    try:
        hrs  = int(input("Hours to look back (e.g. 24): ").strip())
        topn = int(input("How many top posts? (0 = all): ").strip())
    except ValueError:
        print("ERROR: integers only.", file=sys.stderr); sys.exit(1)

    grab = cfg["output"].get("include_comments", False)
    if grab:
        grab = input("Fetch comments & links? (y/N): ").strip().lower().startswith("y")

    total, posts = fetch_posts(subr, hrs, topn)
    out_dir = cfg["output"]["local_dir"]
    md_path = write_markdown(subr, hrs, total, posts, grab, out_dir)
    print(f"Saved markdown to {md_path}")

    do_upload = False
    if GOOGLE_AVAILABLE:
        ans = input("Upload to Google Drive as Doc? (y/N): ").strip().lower()
        do_upload = ans.startswith("y")
    if do_upload:
        drive, docs = setup_google_clients()
        folder_id = ensure_drive_folder(cfg["drive"]["folder_name"], drive)
        upload_markdown_as_doc(md_path, folder_id, drive, docs)
    elif not GOOGLE_AVAILABLE:
        print("Google libraries not installed—skipping upload.")

if __name__ == "__main__":
    main()
