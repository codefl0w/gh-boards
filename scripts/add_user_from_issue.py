#!/usr/bin/env python3
"""
Issue Ops Bot: Processes GitHub Issues to add/update user manifests.
Validates ownership, rate limits, and schema before committing.
"""
import sys
import os
import json
import re
import time
import subprocess
from pathlib import Path
from datetime import datetime, timezone

# --- Configuration ---
USERS_DIR = Path("users")


def get_iso_now() -> str:
    """Return current UTC time in ISO8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validation_fail(message):
    print(f"::error::{message}")
    sys.exit(1)


def get_last_commit_time(filepath):
    """Returns the unix timestamp of the last commit to the file."""
    if not filepath.exists():
        return 0
    try:
        output = subprocess.check_output(
            ["git", "log", "-1", "--format=%ct", str(filepath)], text=True
        ).strip()
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
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", issue_body)
    if json_match:
        raw_json = json_match.group(1)
    else:
        raw_json = issue_body.strip()

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        validation_fail(
            "Could not find valid JSON in the issue body. Please wrap your config in ```json ... ``` blocks."
        )

    # 3. Validation: Ownership & Username
    target_user = data.get("user")

    if not target_user:
        print(f"No 'user' field in JSON. Injecting '{issue_author}'.")
        data["user"] = issue_author
        target_user = issue_author

    if target_user.lower() != issue_author.lower():
        validation_fail(
            f"Permission Denied: Issue author '{issue_author}' cannot create/edit manifest for '{target_user}'."
        )

    # 4. Validation: File Path
    safe_filename = re.sub(r"[^a-zA-Z0-9_-]", "", target_user)
    target_file = USERS_DIR / f"{safe_filename}.json"

    # 5. Validation: Rate Limiting (5 minutes cooldown)
    last_commit_ts = get_last_commit_time(target_file)
    now_ts = int(time.time())
    if now_ts - last_commit_ts < 300:
        validation_fail(
            "Rate Limit Exceeded: You updated this file less than 5 minutes ago. Please wait."
        )

    # 6. Schema Validation & Normalization
    # Ensure schema_version
    if "schema_version" not in data:
        data["schema_version"] = 1

    # Ensure defaults
    if not isinstance(data.get("defaults"), dict):
        data["defaults"] = {"theme": "dark", "visibility": "public", "max_repos": 10}

    # Ensure artifacts is list
    if "artifacts" in data and not isinstance(data["artifacts"], list):
        validation_fail("'artifacts' must be a list.")

    # 7. Update Timestamps
    now = get_iso_now()
    
    # Check if this is an update or new file
    if target_file.exists():
        # Preserve created_on from existing file
        try:
            with open(target_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
                data["created_on"] = existing.get("created_on", now)
        except Exception:
            data["created_on"] = now
    else:
        data["created_on"] = now

    data["last_update"] = now

    # Update meta section
    if "meta" not in data:
        data["meta"] = {}
    data["meta"]["last_processed_by"] = "issue-ops"
    data["meta"]["last_processed_at"] = now

    # 8. Write File
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
