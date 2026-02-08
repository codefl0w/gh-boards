#!/usr/bin/env python3
"""
Batch generator for gh-boards.
Processes all user manifests in ./users and generates SVG artifacts.
Supports schema_version 1 manifests with timestamps and artifact metadata.
"""
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Any

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
OUTPUT_DIR = PROJECT_ROOT / "out"  # Hardcoded, not user-configurable


def get_iso_now() -> str:
    """Return current UTC time in ISO8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def save_manifest(path: Path, cfg: Dict[str, Any]) -> None:
    """Write updated manifest back to disk."""
    with path.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def process_manifest(path: Path, headers: Dict[str, str]) -> None:
    cfg = load_user_manifest(path)
    if not cfg:
        print(f"[SKIP] Empty or invalid manifest: {path}", file=sys.stderr)
        return

    # Schema version check
    schema_version = cfg.get("schema_version", 0)
    username = (str(cfg.get("user")).strip() if cfg.get("user") else "") or path.stem

    # Global defaults
    defaults = cfg.get("defaults", {})
    default_theme = defaults.get("theme", "dark")

    # Select policy
    select = cfg.get("select", {})
    method = str(select.get("method", "top_stars"))
    limit = int(select.get("limit", 20) or 20)

    # Determine repo list
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

    # Compute stats for all selected repos
    print(f"[{username}] Gathering data for {len(repos_data)} repos (method={method}, limit={limit})...")
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
        # Fallback for legacy manifests
        artifacts = [{
            "id": "board",
            "type": "board",
            "style": "board_stars_downloads",
            "options": {"max_repos": 10, "show_stars": True}
        }]
        cfg["artifacts"] = artifacts

    out_dir = OUTPUT_DIR / username
    manifest_updated = False

    for art in artifacts:
        art_type = art.get("type", "board")
        art_style = art.get("style", "board_stars_downloads")
        art_status = art.get("status", "active")

        # Skip paused artifacts
        if art_status == "paused":
            continue

        # Currently only support board type
        if art_type != "board":
            print(f"[{username}] Skipping unsupported artifact type: {art_type}")
            continue

        art_id = art.get("id", "board")
        
        # Build options: merge defaults with artifact-specific options
        opts = {
            "theme": art.get("theme", default_theme),
            "show_stars": True,
            "show_downloads": True
        }
        opts.update(art.get("options", {}))

        # Filter rows based on max_repos
        max_repos = int(opts.get("max_repos", 10))
        sorted_rows = sorted(base_rows, key=lambda x: x[1], reverse=True)
        final_rows = sorted_rows[:max_repos]

        out_file = out_dir / f"{art_id}.svg"
        render_svg(username, final_rows, out_file, options=opts)
        print(f"[{username}] Wrote {out_file} (rows={len(final_rows)})")

        # Update artifact metadata
        art["last_rendered_at"] = get_iso_now()
        art["canonical_url"] = f"https://codefl0w.github.io/web-tools/gh-boards/out/{username}/{art_id}.svg"
        manifest_updated = True

    # Update manifest timestamps
    if manifest_updated:
        cfg["last_update"] = get_iso_now()
        if "meta" not in cfg:
            cfg["meta"] = {}
        cfg["meta"]["last_processed_by"] = "scripts/generate_batch"
        cfg["meta"]["last_processed_at"] = get_iso_now()
        save_manifest(path, cfg)
        print(f"[{username}] Updated manifest with timestamps")


def main() -> None:
    if not USERS_DIR.exists():
        print("No ./users directory found. Create users/<username>.json and re-run.", file=sys.stderr)
        sys.exit(1)

    # Load secrets (for local dev) or use env var (for GitHub Actions)
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
