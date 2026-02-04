#!/usr/bin/env python3
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import importlib

# Add project root to sys.path to allow imports from core/ and boards/
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.append(str(PROJECT_ROOT))

# Core imports
from core.utils import load_user_manifest, load_secrets
from core.github_client import build_headers, fetch_repo, fetch_top_starred_repos, fetch_all_repos, repo_downloads

from boards.board_stars_downloads import render_svg

# Constants
USERS_DIR = PROJECT_ROOT / "users"
SECRETS_PATH = PROJECT_ROOT / "secrets.json"

def process_manifest(path: Path, headers: Dict[str, str]) -> None:
    cfg = load_user_manifest(path)
    username = (str(cfg.get("user")).strip() if cfg.get("user") else "") or path.stem

    # Global defaults for the manifest
    defaults = cfg.get("defaults", {})
    output_base_dir = PROJECT_ROOT / Path(defaults.get("output_dir", "out"))

    # Select policy
    select = cfg.get("select", {})
    method = str(select.get("method", "top_stars"))
    limit = int(select.get("limit", 20) or 20)

    # Determine repo list efficiently
    repos_data: List[dict] = []
    try:
        explicit_repos = cfg.get("targets", {}).get("repos")
        if explicit_repos and isinstance(explicit_repos, list):
            for rname in explicit_repos:
                repo_json = fetch_repo(username, rname, headers)
                if repo_json:
                    repos_data.append(repo_json)
        elif method == "top_stars":
            try:
                repos_data = fetch_top_starred_repos(username, headers, limit)
                if not repos_data:
                    repos_data = fetch_all_repos(username, headers)
            except Exception:
                repos_data = fetch_all_repos(username, headers)
        else:
            repos_data = fetch_all_repos(username, headers)
    except Exception as e:
        print(f"[{username}] Failed to fetch repo list: {e}", file=sys.stderr)
        return

    # Compute stats for all selected repos once
    print(f"[{username}] Gathering data for {len(repos_data)} repos (selected method={method}, limit={limit})...")
    base_rows: List[Tuple[str, int, int]] = []
    
    for r in repos_data:
        name = r.get("name")
        if not name:
            continue
        stars = int(r.get("stargazers_count", 0) or 0)
        try:
            dls = repo_downloads(username, name, headers)
        except Exception:
            dls = 0
        base_rows.append((name, dls, stars))

    # Identify artifacts to render
    artifacts = cfg.get("artifacts")
    if not artifacts or not isinstance(artifacts, list):
        # Fallback for simple/legacy manifests: generate default board
        processed_artifacts = [{
            "id": f"{username}_board",
            "type": "board",
            "options": defaults
        }]
    else:
        processed_artifacts = artifacts

    out_dir = output_base_dir / username

    for art in processed_artifacts:
        art_type = art.get("type", "board")
        # simplistic filtering: this script currently defaults to board_stars_downloads
        # In a full system, we would map art_type to specific renderers
        if art_type != "board":
            continue

        art_id = art.get("id", "board")
        # Merge options: global defaults < artifact options
        opts = defaults.copy()
        opts.update(art.get("options", {}))

        # Filter rows based on max_repos
        max_repos = opts.get("max_repos", 20)
        
        # Sort by downloads descending by default for the board
        sorted_rows = sorted(base_rows, key=lambda x: x[1], reverse=True)
        final_rows = sorted_rows[:int(max_repos)]

        out_file = out_dir / f"{art_id}.svg"
        render_svg(username, final_rows, out_file, options=opts)
        print(f"[{username}] Wrote {out_file} (rows={len(final_rows)})")

def main() -> None:
    if not USERS_DIR.exists():
        print("No ./users directory found. Create users/<username>.json and re-run.", file=sys.stderr)
        sys.exit(1)

    secrets = load_secrets(SECRETS_PATH)
    headers = build_headers(secrets)

    manifests = sorted(USERS_DIR.glob("*.json"))
    if not manifests:
        print("No user manifests found in ./users. Create users/<username>.json and re-run.")
        return

    for m in manifests:
        try:
            process_manifest(m, headers)
        except Exception as e:
            print(f"Failed processing {m}: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
