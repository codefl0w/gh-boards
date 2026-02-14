"""
Vercel serverless function for on-demand badge generation.
Usage: /api/badge?user=X&repo=Y&type=stars|downloads&color=...&label_color=...&text_style=...
"""
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.append(str(PROJECT_ROOT))

from core.github_client import fetch_repo, repo_downloads, build_headers
from badges.badge import generate_badge_svg


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # CORS
        allowed_origins = [
            "https://codefl0w.github.io",
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

        if not user or not repo:
            err = (
                '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="20">'
                '<rect width="200" height="20" rx="3" fill="#e05d44"/>'
                '<text x="100" y="14" fill="#fff" font-family="sans-serif" '
                'font-size="11" text-anchor="middle">error: user &amp; repo required</text>'
                '</svg>'
            )
            self.wfile.write(err.encode("utf-8"))
            return

        # Auth
        token = os.environ.get("GITHUB_TOKEN")
        headers = {"User-Agent": "gh-boards/1.0", "Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            if badge_type == "downloads":
                value = repo_downloads(user, repo, headers)
            else:
                # Stars — fetch repo metadata
                repo_data = fetch_repo(user, repo, headers)
                value = int((repo_data or {}).get("stargazers_count", 0))

            options = {
                "badge_type": badge_type,
                "color": color,
                "label_color": label_color,
                "text_style": text_style,
            }
            svg = generate_badge_svg(user, repo, value, options)
            self.wfile.write(svg.encode("utf-8"))

        except Exception as e:
            err = (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="250" height="20">'
                f'<rect width="250" height="20" rx="3" fill="#e05d44"/>'
                f'<text x="125" y="14" fill="#fff" font-family="sans-serif" '
                f'font-size="11" text-anchor="middle">error: {str(e)[:40]}</text>'
                f'</svg>'
            )
            self.wfile.write(err.encode("utf-8"))
