#!/usr/bin/env python3
"""
Batch generator for gh-boards.
Processes all user manifests in ./users and generates SVG artifacts.
Supports schema_version 1 manifests with timestamps, artifact metadata, and ETag caching.
"""
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Any, Optional

# Add project root to sys.path to allow imports from core/ and boards/
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.append(str(PROJECT_ROOT))

# Core imports
from core.utils import load_user_manifest, load_secrets
from core.github_client import (
    build_headers, fetch_repo, fetch_top_starred_repos_with_etag,
    fetch_all_repos, repo_downloads
)

from boards.board_stars_downloads import render_svg
from badges.badge import render_badge_svg

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

    username = (str(cfg.get("user")).strip() if cfg.get("user") else "") or path.stem

    # Global defaults
    defaults = cfg.get("defaults", {})
    default_theme = defaults.get("theme", "dark")

    # Select policy
    select = cfg.get("select", {})
    method = str(select.get("method", "top_stars"))

    # Cache section
    cache = cfg.get("cache", {})
    cached_etag = cache.get("repos_etag")

    # Determine max_repos from first board artifact
    artifacts = cfg.get("artifacts", [])
    max_repos = 10
    for art in artifacts:
        if art.get("type") == "board":
            max_repos = int(art.get("options", {}).get("max_repos", 10))
            break

    # ========== ETag-based conditional fetch ==========
    repos_data: List[dict] = []
    new_etag: Optional[str] = None
    data_changed = True  # Assume changed unless proven otherwise

    try:
        explicit_repos = cfg.get("targets", {}).get("repos")
        if explicit_repos and isinstance(explicit_repos, list):
            # Explicit repos: always fetch (no ETag for individual repos)
            for rname in explicit_repos:
                repo_json = fetch_repo(username, rname, headers)
                if repo_json:
                    repos_data.append(repo_json)
        elif method == "top_stars":
            # Use ETag caching for top_stars method
            repos_data_result, new_etag, data_changed = fetch_top_starred_repos_with_etag(
                username, headers, max_repos, cached_etag
            )
            
            if not data_changed:
                # Data hasn't changed - skip rendering entirely
                print(f"[{username}] No changes detected (ETag match). Skipping render.")
                # Update last_checked timestamp
                cache["last_checked"] = get_iso_now()
                cfg["cache"] = cache
                save_manifest(path, cfg)
                return
            
            repos_data = repos_data_result or []
            if not repos_data:
                repos_data = fetch_all_repos(username, headers)
        else:
            repos_data = fetch_all_repos(username, headers)
    except Exception as e:
        print(f"[{username}] Failed to fetch repo list: {e}", file=sys.stderr)
        return

    # Compute stats for all selected repos
    print(f"[{username}] Gathering data for {len(repos_data)} repos (method={method})...")
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

    # Update cache with new ETag
    if new_etag:
        cache["repos_etag"] = new_etag
    cache["last_checked"] = get_iso_now()
    cfg["cache"] = cache

    # Identify artifacts to render
    if not artifacts:
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
        art_status = art.get("status", "active")

        # Skip paused artifacts
        if art_status == "paused":
            continue

        art_id = art.get("id", art_type)

        if art_type == "board":
            # Build options
            opts = {
                "theme": art.get("theme", default_theme),
                "show_stars": True,
                "show_downloads": True
            }
            opts.update(art.get("options", {}))

            # Filter rows based on max_repos
            art_max_repos = int(opts.get("max_repos", 10))
            sorted_rows = sorted(base_rows, key=lambda x: x[1], reverse=True)
            final_rows = sorted_rows[:art_max_repos]

            out_file = out_dir / f"{art_id}.svg"
            render_svg(username, final_rows, out_file, options=opts)
            print(f"[{username}] Wrote {out_file} (rows={len(final_rows)})")

        elif art_type == "badge":
            opts = art.get("options", {})
            badge_type = opts.get("badge_type", "stars")
            target_repo = opts.get("repo", "")

            # Followers is user-level — no repo needed
            if badge_type != "followers" and not target_repo:
                print(f"[{username}] Badge '{art_id}' missing 'repo' option, skipping")
                continue

            # ── Resolve value based on badge_type ──
            if badge_type == "stars":
                match = [r for r in base_rows if r[0] == target_repo]
                if match:
                    value = match[0][2]  # stars
                else:
                    from core.github_client import fetch_repo as _fetch_repo
                    repo_json = _fetch_repo(username, target_repo, headers)
                    value = int((repo_json or {}).get("stargazers_count", 0))

            elif badge_type == "downloads":
                match = [r for r in base_rows if r[0] == target_repo]
                if match:
                    value = match[0][1]  # downloads
                else:
                    try:
                        value = repo_downloads(username, target_repo, headers)
                    except Exception:
                        value = 0

            elif badge_type == "followers":
                from core.github_client import fetch_followers_count
                value = fetch_followers_count(username, headers)

            elif badge_type == "watchers":
                from core.github_client import fetch_watchers_count
                value = fetch_watchers_count(username, target_repo, headers)

            elif badge_type == "workflow_status":
                from core.github_client import fetch_latest_workflow_run, workflow_status_label
                wf = opts.get("workflow") or None
                run, _, _ = fetch_latest_workflow_run(username, target_repo, headers, wf)
                status_text, status_color = workflow_status_label(run)
                value = status_text
                opts["color"] = status_color
                if wf:
                    opts["workflow"] = wf

            else:
                print(f"[{username}] Unknown badge_type '{badge_type}', skipping")
                continue

            out_file = out_dir / f"{art_id}.svg"
            render_badge_svg(username, target_repo, value, out_file, opts)
            print(f"[{username}] Wrote badge {out_file} ({badge_type}={value})")

        else:
            print(f"[{username}] Skipping unsupported artifact type: {art_type}")
            continue

        # Update artifact metadata
        art["last_rendered_at"] = get_iso_now()
        art["canonical_url"] = f"https://codefl0w.xyz/gh-boards/out/{username}/{art_id}.svg"
        manifest_updated = True

    # Update manifest timestamps
    if manifest_updated:
        cfg["last_update"] = get_iso_now()
        if "meta" not in cfg:
            cfg["meta"] = {}
        cfg["meta"]["last_processed_by"] = "scripts/generate_batch"
        cfg["meta"]["last_processed_at"] = get_iso_now()
        save_manifest(path, cfg)
        print(f"[{username}] Updated manifest with timestamps and cache")


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
