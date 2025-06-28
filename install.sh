#!/usr/bin/env bash
set -euo pipefail

# One-line installer for reddit-digest
# Usage: bash <(curl -s https://raw.githubusercontent.com/farsonic/reddit-digest/main/install.sh)

# 1️⃣ Clone (or pull) the repo
if [ -d "reddit-digest" ]; then
    echo "Updating existing reddit-digest directory..."
    cd reddit-digest && git pull origin main
else
    echo "Cloning reddit-digest..."
    git clone https://github.com/farsonic/reddit-digest.git
    cd reddit-digest
fi

# 2️⃣ Create a virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# 3️⃣ Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install praw google-api-python-client google-auth google-auth-httplib2 google-auth-oauthlib

# 4️⃣ Reminder: configure credentials
cat <<EOF

✅ Setup complete.

Next steps:
 1. Copy and edit config.json with your Reddit API credentials.
 2. Place your OAuth client JSON (gdrive-creds.json) in this folder.
 3. Run the script: python3 reddit_digest.py
EOF

