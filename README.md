# Reddit Digest - NotebookLM ingest

[<img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px; width: 217px" />](https://buymeacoffee.com/farsonic)

A Python script to fetch top posts (and optional comments/links) from a Reddit subreddit within a defined time window, render them to Markdown, and optionally convert to a Google Doc and upload to your personal Google Drive. There is also the ability to hardcode specific subreddits in a local config file as well as specific stock, commodities and weather to embed into the Markdown. The expectation is that once the specified groups have been converted to markdown they can be uploaded into NotepadLM for analysis and podcast creation. 

---

## Features

- Fetch posts from any single or group of public subreddits over the last _N_ hours  
- Return either all or top _X_ posts by score, with the score stored in the resulting markdown file.
- Optionally extract top-level comments and any URLs within them  
- Generate a timestamped Markdown report locally
- Embed specific stocks, commodites and local weather URL's into the markdown text. 
- Convert the Markdown to a Google Doc  
- Upload the Doc into a specified folder in your personal Drive  

---

## Repository Layout

```
reddit-digest/
├── config.json         # Reddit + Drive configuration
├── gdrive-creds.json   # OAuth client JSON from Google
├── token.json          # Cached OAuth tokens (auto-generated)
├── reddit-notepad.py   # Main Python script
└── install.sh          # Installer script
```

---

## Prerequisites

1. **Python & pip**  
   - Python 3.8+  
   - `pip3` installed  

2. **Google Cloud Project Setup (Optional)**  
   1. **Enable APIs**  
      - Go to **APIs & Services → Library**, search for _Google Drive API_ and _Google Docs API_, and click **Enable** on each.  
   2. **Configure OAuth consent screen**  
      - In **APIs & Services → OAuth consent screen**, choose **External**.  
      - Fill in **App name** (e.g. “Reddit Notepad Uploader”) and **User support email**.  
      - Under **Scopes**, add:  
        ```
        https://www.googleapis.com/auth/drive.file
        https://www.googleapis.com/auth/documents
        ```  
      - Under **Test users**, add your Google email, then **Publish**.  
   3. **Create OAuth Client ID**  
      - In **APIs & Services → Credentials**, click **Create Credentials → OAuth client ID**.  
      - Choose **Desktop app**, name it, and download the JSON as `gdrive-creds.json`.  

3. **Git** (for installer)  

---

## config.json

Create a `config.json` in the root of this repo with **your** Reddit & Drive settings:

```json
{
  "reddit": {
    "client_id":            "",      /* Your Reddit API client ID */
    "client_secret":        "",      /* Your Reddit API client secret */
    "user_agent":           "",      /* Your app’s user agent string */
    "comment_age_threshold_days": 0  /* Ignore comments from accounts younger than this */
  },

  "subreddits": [
    /* List your subreddits here, e.g. "worldnews", "tech" */
  ],

  "default": {
    "hours":     0,  /* Look back this many hours */
    "top_posts": 0   /* Number of top posts (0 = all new posts) */
  },

  "output": {
    "local_dir":        "",      /* Where to save the .md files */
    "include_comments": false    /* true to pull comments & links */
  },

  "drive": {
    "enabled":          false,  /* true to enable Google Drive upload */
    "credentials_file": "",     /* Path to your OAuth client JSON */
    "folder_name":      ""      /* Name of the Drive folder to use */
  },

  "urls": {
    "stocks": [
      /* e.g. "https://finance.yahoo.com/quote/AMD/" */
    ],
    "commodities": [
      /* e.g. "https://finance.yahoo.com/quote/GC=F/" */
    ],
    "fx": [
      /* e.g. "https://finance.yahoo.com/quote/AUDUSD=X/" */
    ],
    "weather": ""  /* e.g. "https://www.accuweather.com/…" */
  }
}
```

---

## Python Dependencies

Install via pip:

```bash
pip3 install praw \
  google-api-python-client \
  google-auth \
  google-auth-httplib2 \
  google-auth-oauthlib
```

---

## Usage

1. **Run the script**  
   ```bash
   python3 reddit-notepad.py
   ```  
   You’ll be prompted for:  
   - **Subreddit** (e.g. `worldnews`)  
   - **Hours back** (e.g. `24`)  
   - **Top posts** (enter `0` for all)  
   - **Fetch comments & links?** (`y` or `n`)  

   On first Drive upload, a browser window will open—choose your Google account and grant the requested scopes. A `token.json` will be saved locally.

2. **Check your outputs**  
   - **Local** Markdown file in `./output/`  
   - **Google Doc** in **My Drive → Reddit Reports**  

---

## Installer Script

Install in one line:

```bash
bash <(curl -s https://raw.githubusercontent.com/farsonic/reddit-digest/main/install.sh)
```

This will clone or update the repo, create a virtual environment, install all Python deps, and prompt you to configure `config.json` & place `gdrive-creds.json`.

---

## License

MIT © Your Name
