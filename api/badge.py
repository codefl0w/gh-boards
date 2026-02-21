"""
Vercel serverless function for on-demand badge generation.

Supported types:
  /api/badge?user=X&repo=Y&type=stars|downloads|watchers|workflow_status
  /api/badge?user=X&type=followers          (no repo needed)
  /api/badge?user=X&repo=Y&type=workflow_status&workflow=ci.yml  (optional)

Common params: color, label_color, text_style
"""
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.append(str(PROJECT_ROOT))

from core.github_client import (
    fetch_repo,
    repo_downloads,
    fetch_followers_count,
    fetch_watchers_count,
    fetch_latest_workflow_run,
    workflow_status_label,
)
from badges.badge import generate_badge_svg


def _error_svg(msg: str, width: int = 250) -> bytes:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="20">'
        f'<rect width="{width}" height="20" rx="3" fill="#e05d44"/>'
        f'<text x="{width // 2}" y="14" fill="#fff" font-family="sans-serif" '
        f'font-size="11" text-anchor="middle">{msg}</text>'
        f'</svg>'
    ).encode("utf-8")


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # CORS
        allowed_origins = [
            "codefl0w.xyz",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
        origin = self.headers.get("Origin")

        self.send_response(200)
        self.send_header("Content-type", "image/svg+xml; charset=utf-8")
        self.send_header("Cache-Control", "s-maxage=43200, stale-while-revalidate=86400")

        if origin and any(allowed in origin for allowed in allowed_origins):
            self.send_header("Access-Control-Allow-Origin", origin)
        else:
            self.send_header("Access-Control-Allow-Origin", "*")

        self.end_headers()

        # Parse params
        query = parse_qs(urlparse(self.path).query)
        user = query.get("user", [""])[0]
        repo = query.get("repo", [""])[0]
        badge_type = query.get("type", ["stars"])[0]
        color = query.get("color", ["#2ea44f"])[0]
        label_color = query.get("label_color", ["#555"])[0]
        text_style = query.get("text_style", ["normal"])[0]
        workflow = query.get("workflow", [""])[0]
        label = query.get("label", [""])[0]

        if not user:
            self.wfile.write(_error_svg("error: user required"))
            return

        # repo is required for everything except followers
        if badge_type != "followers" and not repo:
            self.wfile.write(_error_svg("error: repo required"))
            return

        # Auth
        token = os.environ.get("GITHUB_TOKEN")
        headers = {"User-Agent": "gh-boards/1.0", "Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            value = 0  # default
            badge_opts = {
                "badge_type": badge_type,
                "color": color,
                "label_color": label_color,
                "text_style": text_style,
            }
            if label: # Added label to badge_opts if present
                badge_opts["label"] = label

            if badge_type == "stars":
                repo_data = fetch_repo(user, repo, headers)
                value = int((repo_data or {}).get("stargazers_count", 0))

            elif badge_type == "downloads":
                value = repo_downloads(user, repo, headers)

            elif badge_type == "followers":
                value = fetch_followers_count(user, headers)

            elif badge_type == "watchers":
                value = fetch_watchers_count(user, repo, headers)

            elif badge_type == "workflow_status":
                wf = workflow or None
                run, _, _ = fetch_latest_workflow_run(user, repo, headers, wf)
                status_text, status_color = workflow_status_label(run)
                value = status_text
                # Override color with status-driven color
                badge_opts["color"] = status_color
                if run and run.get("name"):
                    badge_opts["workflow_name"] = run.get("name")
                if wf:
                    badge_opts["workflow"] = wf

            elif badge_type == "license":
                repo_data = fetch_repo(user, repo, headers)
                lic = (repo_data or {}).get("license") or {}
                value = lic.get("name") or "no license"
                if not lic.get("name"):
                    badge_opts["color"] = "#d73a49"

            else:
                self.wfile.write(_error_svg(f"unknown type: {badge_type}"))
                return

            svg = generate_badge_svg(user, repo, value, badge_opts)
            self.wfile.write(svg.encode("utf-8"))

        except Exception as e:
            self.wfile.write(_error_svg(f"error: {str(e)[:40]}"))
