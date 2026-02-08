import os
import requests
from typing import Dict, List, Optional, Tuple

API = "https://api.github.com"
TIMEOUT = 10
MAX_PER_PAGE = 100


def build_headers(secrets: Dict[str, str]) -> Dict[str, str]:
    headers = {"User-Agent": "gh-boards-generator/1.1", "Accept": "application/vnd.github+json"}
    # Check secrets.json first, then fall back to env var (GitHub Actions)
    token = secrets.get("GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_top_starred_repos_with_etag(
    user: str, headers: Dict[str, str], limit: int, etag: Optional[str] = None
) -> Tuple[Optional[List[dict]], Optional[str], bool]:
    """
    Fetch top starred repos with ETag support.
    
    Returns: (data, new_etag, changed)
    - If 304 Not Modified: (None, old_etag, False)
    - If 200 OK: (repos_list, new_etag, True)
    """
    if limit <= 0:
        return [], None, False
    
    q = f"user:{user}"
    params = {"q": q, "sort": "stars", "order": "desc", "per_page": str(limit)}
    url = f"{API}/search/repositories"
    
    req_headers = headers.copy()
    if etag:
        req_headers["If-None-Match"] = etag
    
    r = requests.get(url, headers=req_headers, params=params, timeout=TIMEOUT)
    
    if r.status_code == 304:
        # Not modified - data hasn't changed
        return None, etag, False
    
    r.raise_for_status()
    data = r.json()
    items = data.get("items") or []
    new_etag = r.headers.get("ETag")
    
    return items[:limit], new_etag, True


def fetch_top_starred_repos(user: str, headers: Dict[str, str], limit: int) -> List[dict]:
    """
    Use the Search API to get user's repositories ordered by stars.
    Returns up to `limit` repo objects.
    """
    repos, _, _ = fetch_top_starred_repos_with_etag(user, headers, limit, None)
    return repos or []


def fetch_all_repos(user: str, headers: Dict[str, str]) -> List[dict]:
    url = f"{API}/users/{user}/repos?per_page={MAX_PER_PAGE}"
    out: List[dict] = []
    while url:
        r = requests.get(url, headers=headers, timeout=TIMEOUT)
        r.raise_for_status()
        out.extend(r.json())
        url = r.links.get("next", {}).get("url")
    return out


def fetch_repo(user: str, repo: str, headers: Dict[str, str]) -> Optional[dict]:
    url = f"{API}/repos/{user}/{repo}"
    r = requests.get(url, headers=headers, timeout=TIMEOUT)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def repo_downloads(owner: str, repo: str, headers: Dict[str, str]) -> int:
    url = f"{API}/repos/{owner}/{repo}/releases?per_page={MAX_PER_PAGE}"
    total = 0
    while url:
        r = requests.get(url, headers=headers, timeout=TIMEOUT)
        if r.status_code == 404:
            return 0
        r.raise_for_status()
        rels = r.json()
        for rel in rels:
            for asset in (rel.get("assets") or []):
                try:
                    total += int(asset.get("download_count", 0) or 0)
                except Exception:
                    pass
        url = r.links.get("next", {}).get("url")
    return total
