# INSTRUCTIONS — gh-boards

This document records the full design, implementation plan, file contracts, runtime behavior, and operational guidance for **gh-boards** (the static GitHub-profile badge/board generator).

## 1 — Project summary

A static artifact generator that reads per-user manifests stored in `users/<username>.json`, fetches GitHub data on a scheduled runner, renders deterministic SVG boards, and serves them via GitHub Pages. A client-side web interface at `web/` allows users to generate these manifests.

---

## 2 — Core principles

1. **One manifest per user**: `users/<username>.json`.
2. **Static & Scheduled**: SVGs are pre-computed by a scheduled Action, not on-demand.
3. **Web Configurator**: Users build configs via the web UI, then commit the JSON to the repo.
4. **No per-request API calls**: Badges are static files in `out/`, updated hourly.

---

## 3 — Repository layout

```
gh-boards/
├─ users/                 # manifest JSON files
├─ out/                   # generated SVGs (out/<username>/<id>.svg)
├─ web/                   # Frontend config generator (index.html, app.js)
├─ core/                  # Shared logic (utils.py, github_client.py)
├─ boards/                # Board renderers (board_stars_downloads.py)
├─ scripts/               # Orchestrator (generate_batch.py)
├─ .github/workflows/     # Actions workflow (generate.yml)
├─ requirements.txt
├─ README.md
└─ INSTRUCTIONS.md
```

---

## 4 — Manifest: schema and contract

**File path:** `users/{username}.json`

```json
{
  "user": "octocat",
  "defaults": { "theme": "dark", "output_dir": "out" },
  "select": { "method": "top_stars", "limit": 20 },
  "artifacts": [
    {
      "id": "my_board",
      "type": "board",
      "options": { "max_repos": 10, "show_stars": true }
    }
  ]
}
```

---

## 5 — Web Frontend (Config Generator)

Located in `web/`.
- **Goal**: Allow users to visually configure their board and download the JSON.
- **Hosting**: GitHub Pages (alongside the `out/` directory).
- **Flow**: User visits site -> Configures Board -> Downloads JSON -> Commits to `users/` -> Action runs.

---

## 6 — Worker & Orchestration

**Entrypoint:** `scripts/generate_batch.py`

1. Loads all `users/*.json`.
2. Sorts by oldest update to ensure fair scheduling.
3. Defines a batch size (default 20) to respect API quotas.
4. For each user:
   - Fetches repos (via `core/github_client`).
   - Computes stats.
   - Invokes renderers in `boards/`.
   - Saves SVGs to `out/<username>/`.
5. Commits changes to the repo.

**Refactoring Note**: 
- `core/` contains API clients and utilities.
- `boards/` contains pure SVG rendering functions.
- `scripts/` contains the batch processing logic.

---

## 7 — Actions workflow

`.github/workflows/generate.yml` runs `python scripts/generate_batch.py` on a schedule (e.g., hourly).

---

## 8 — Security & Quotas

- **Rate Limits**: The worker respects GitHub API limits using token authentication.
- **Batching**: Only process N manifests per run to prevent timeout/quota exhaustion.

