#!/usr/bin/env python3
import sys
import os
import json
import re
import time
import subprocess
from pathlib import Path

# --- Configuration ---
USERS_DIR = Path("users")

def validation_fail(message):
    print(f"::error::{message}")
    sys.exit(1)

def get_last_commit_time(filepath):
    """Returns the unix timestamp of the last commit to the file."""
    if not filepath.exists():
        return 0
    try:
        # git log -1 --format=%ct <file>
        output = subprocess.check_output(["git", "log", "-1", "--format=%ct", str(filepath)], text=True).strip()
        return int(output) if output else 0
    except subprocess.CalledProcessError:
        return 0

def main():
    # 1. Inputs from Environment (GitHub Actions)
    issue_author = os.environ.get("ISSUE_AUTHOR", "").strip()
    issue_body = os.environ.get("ISSUE_BODY", "")
    
    if not issue_author:
        validation_fail("Missing ISSUE_AUTHOR environment variable.")

    print(f"Processing request from: {issue_author}")

    # 2. Extract JSON from Issue Body
    # Look for code blocks ```json ... ``` or just the raw body if it looks like JSON
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", issue_body)
    if json_match:
        raw_json = json_match.group(1)
    else:
        # Try raw body if no code blocks
        raw_json = issue_body.strip()

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        validation_fail("Could not find valid JSON in the issue body. Please wrap your config in ```json ... ``` blocks.")

    # 3. Validation: Ownership & Username
    # "Issue author.login must equal the requested manifest.user"
    target_user = data.get("user")
    
    if not target_user:
        print(f"No 'user' field in JSON. Injecting '{issue_author}'.")
        data["user"] = issue_author
        target_user = issue_author
    
    if target_user.lower() != issue_author.lower():
        validation_fail(f"Permission Denied: Issue author '{issue_author}' cannot create/edit manifest for '{target_user}'.")

    # 4. Validation: File Path
    # "Only allowed paths may be written: users/{username}.json"
    safe_filename = re.sub(r"[^a-zA-Z0-9_-]", "", target_user)
    target_file = USERS_DIR / f"{safe_filename}.json"
    
    # 5. Validation: Rate Limiting
    # "Reject if the same user created a manifest commit in the last N minutes" (e.g. 5 mins)
    last_commit_ts = get_last_commit_time(target_file)
    now_ts = int(time.time())
    if now_ts - last_commit_ts < 300: # 300 seconds = 5 minutes
        validation_fail(f"Rate Limit Exceeded: You updated this file less than 5 minutes ago. Please wait.")

    # 6. Validation: Schema (Basic)
    if not isinstance(data.get("defaults"), dict):
         data["defaults"] = {} # Normalize
    
    # ensure "artifacts" is list if present
    if "artifacts" in data and not isinstance(data["artifacts"], list):
        validation_fail("'artifacts' must be a list.")

    # 7. Write File
    USERS_DIR.mkdir(exist_ok=True)
    
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    
    print(f"Successfully wrote manifest to {target_file}")
    
    # Output for next steps
    with open(os.environ["GITHUB_OUTPUT"], "a") as gh_out:
        gh_out.write(f"USER_FILE={target_file}\n")
        gh_out.write(f"USER_NAME={target_user}\n")

if __name__ == "__main__":
    main()
