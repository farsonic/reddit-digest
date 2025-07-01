# Reddit Digest - NotebookLM ingest

[<img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px; width: 217px" />](https://buymeacoffee.com/farsonic)

A Python script to fetch top posts (and optional comments/links) from a Reddit subreddit within a defined time window, render them to Markdown, and optionally convert to a Google Doc and upload to your personal Google Drive. There is also the ability to hardcode specific subreddits in a local config file as well as specific stock, commodities and weather to embed into the Markdown. The expectation is that once the specified groups have been converted to markdown they can be uploaded into NotepadLM for analysis and podcast creation. 

---

## Features

- Fetch posts from any single or group of public subreddits over the last _N_ hours  
- Return either all or top _X_ posts by score, with the score stored in the resulting markdown file.
- Optionally extract top-level comments and any URLs within them, while also ignoring posted with new accounts of a specific age  
- Generate a timestamped Markdown report locally to a nominated directory
- Embed specific stocks, commodites and local weather URL's into the markdown text. 
- Optionally convert the Markdown to a Google Doc  
- Optionally upload the Doc into a specified folder in your personal Drive  

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
   - Python 3.8+  (python3.12-venv) 
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

3. **Others** (for installer)
   - git
   - curl
   - 

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

### 1. Interactive Mode

```bash
python3 reddit-notepad.py
```

On launch you’ll be prompted for:

- **Subreddit** (e.g. `worldnews`)
- **Hours back** (e.g. `24`)
- **Top posts** (`0` = all, or e.g. `10`)
- **Fetch comments & links?** (`y` or `n`)

If Drive upload is enabled in your `config.json`, the first time you choose to upload, a browser window will open to authorize. A `token.json` file will then be saved for subsequent runs.

---

### 2. Fully Non-Interactive (All Flags)

You can override every prompt via flags:

```bash
python3 reddit-notepad.py \
  --subreddits worldnews technews amiga \
  --hours 12 \
  --topn 20 \
  --comments \
  --debug
```

This will:

- Fetch the top 20 posts from **worldnews**, **technews**, and **amiga**, from the last 12 hours
- Include comments & links
- Emit debug logging to stderr
- Use your Drive settings from `config.json` to upload (unless you pass `--no-drive`)

---

### 3. Examples

#### a) Just grab the last 5 new posts from r/networking, no comments, no Drive

```bash
python3 reddit-notepad.py \
  --subreddits networking \
  --hours 24 \
  --topn 5 \
  --no-drive
```

#### b) Scan multiple subreddits, include comments, upload to Drive

```bash
python3 reddit-notepad.py \
  -s worldnews networking technews \
  -H 6 \
  -n 10 \
  -c
```

#### c) Debug run for troubleshooting

```bash
python3 reddit-notepad.py --debug
```

You’ll see detailed logging of API calls, folder creation, etc.

#### d) Use defaults from `config.json` but disable comments

```bash
python3 reddit-notepad.py --no-drive
```

*(This will still run against the subreddits, hours, and top_posts defined under `"default"` in your config, but skip both comments and Drive upload.)*

---

### 4. Output

1. **Local Markdown**
   Saved to the `local_dir` you set in `config.json` (default `./output/`).

2. **Google Doc** (if enabled)
   Placed in **My Drive → _folder_name_** in your account, then in a subfolder named today’s date.

## Installer Script

Install in one line:

```bash
bash <(curl -s https://raw.githubusercontent.com/farsonic/reddit-digest/main/install.sh)
```

This will clone or update the repo, create a virtual environment, install all Python deps, and prompt you to configure `config.json` & place `gdrive-creds.json`.

---

### 5. Create Reddit API Credentials. 

1. ** Create API Key

   From https://reddit.com/prefs/apps create a personal use script using the following as an example. use the personal use script key for the client_id and the secret for client_secret in the config.json file.
   
  <img width="1118" alt="Screenshot 2025-07-01 at 2 32 20 pm" src="https://github.com/user-attachments/assets/5fdf12f0-7094-44f9-b2cd-0efce4b78c8d" />

### 6. NotebookLM ingest 

   You will now have the ability to create a markdown file that will be held locally as well as stored in google drive if requested. You can now take this and load into NotebookLM for analysis. If using this for creating a podcast this is my current working prompt to cusotmise the output. 

```
You are a production-grade podcast writer. Your input is:
  • A list of stock URLs use 
  • A list of commodity URLs
  • A list of FX URLs
  • One weather forecast URL
  • A set of Reddit post URLs grouped by community
  • Read all the URL links provided and use these for analysis of all components.
  • Extract every link from the post, perform deep research on the articles linked and use this as the basis for discussion. The article content is primary concern followed by the comments and sentiment. 


Your job is to output a 10-minute podcast in four parts:

1️⃣ **Quick Markets & Weather (≈30 s)**  
   - State each stock name and say it is trading at the provided amount and the trend for the day  
   - Do the same for commodities and FX.  
   - Read the weather URL once: “Today's weather is..." 

2️⃣ **Headline Segments**  
   For each group (World News → Tech News → Niche Communities → Hobbies):  
   - **Segment title**  
   - **Bullet 1:** “Top story at URL: …” + a one‐sentence **fact** summary pulled **only** from the article title or first line.  
   - **Bullet 2:** Community sentiment (positive/negative/mixed) based on upvotes & comments count—do **not** dive into the comments themselves here.  
   - **Bullet 3 (only if AMD mentioned):** Name the URL and say “AMD mention detected here.”
   - **Pick up to two standout user comments (accounts ≥ 30 days old) that illustrate community reaction briefly—one sentence each.

4️⃣ **Outro Teaser**  
   - One sentence: “See you tomorrow, when we’ll cover…”

**Formatting & Tone**
- Never say hashtag anything
- Reference the site where the story comes from. 
- Use spoken-audio phrasing (“Up first…,” “Listeners are reacting…”).  
- Get immediately to the point of discussion within 5 seconds. 
- Keep each bullet super-tight.    
- Script length: ~10 minutes. 
```

## License

MIT © Your Name
