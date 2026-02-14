from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.append(str(PROJECT_ROOT))

from core.github_client import fetch_top_starred_repos, fetch_all_repos, repo_downloads, build_headers
from boards.board_stars_downloads import generate_svg_content

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Allow requests from the official site and localhost 
        allowed_origins = [
            "https://codefl0w.xyz",
            "http://localhost:3000",
            "http://127.0.0.1:3000"
        ]
        
        origin = self.headers.get("Origin")
    
        
        self.send_response(200)
        self.send_header('Content-type', 'image/svg+xml; charset=utf-8')
        
        # Public Cache: 12 hour (43200s), stale-while-revalidate for 1 day
        self.send_header('Cache-Control', 's-maxage=43200, stale-while-revalidate=86400')
        
        if origin and any(allowed in origin for allowed in allowed_origins):
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        else:
            self.send_header('Access-Control-Allow-Origin', '*')

        self.end_headers()

        # Parse Query Params
        query = parse_qs(urlparse(self.path).query)
        user = query.get('user', [''])[0]
        theme = query.get('theme', ['dark'])[0]
        show_stars = query.get('show_stars', ['true'])[0].lower() == 'true'
        max_repos = int(query.get('max_repos', [10])[0])

        if not user:
            # Return empty or error SVG
            self.wfile.write(b'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="60"><text x="10" y="40" font-family="sans-serif">Error: No user specified</text></svg>')
            return

        # 3. Fetch Data
        token = os.environ.get("GITHUB_TOKEN")
        headers = {}
        if token:
            headers["Authorization"] = f"token {token}"
        
        try:
            # Reuse core logic
            # Note: This executes sequentially which is slower, but simpler for this MVP.
            # Ideally fetch_top_starred_repos and repo_downloads should be parallelized.
            repos_data = fetch_top_starred_repos(user, headers, max_repos)
            if not repos_data:
                repos_data = fetch_all_repos(user, headers)

            base_rows = []
            for r in repos_data:
                name = r.get("name")
                if not name:
                    continue
                stars = int(r.get("stargazers_count", 0) or 0)
                try:
                    dls = repo_downloads(user, name, headers)
                except Exception:
                    dls = 0
                base_rows.append((name, dls, stars))

            # Sort by downloads
            sorted_rows = sorted(base_rows, key=lambda x: x[1], reverse=True)
            final_rows = sorted_rows[:max_repos]

            # 4. Generate SVG
            options = {
                "theme": theme,
                "show_stars": show_stars,
                "max_repos": max_repos
            }
            svg_content = generate_svg_content(user, final_rows, options)
            self.wfile.write(svg_content.encode('utf-8'))

        except Exception as e:
            err_svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="60"><text x="10" y="40" font-family="sans-serif">Generation Failed: {str(e)}</text></svg>'
            self.wfile.write(err_svg.encode('utf-8'))
