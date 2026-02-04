import json
from pathlib import Path
from typing import Dict, Optional, Any
import sys

def load_json_file(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to load JSON {path}: {e}", file=sys.stderr)
        return None

def load_user_manifest(path: Path) -> Dict[str, Any]:
    data = load_json_file(path)
    return data if isinstance(data, dict) else {}

def load_secrets(secrets_path: Path) -> Dict[str, str]:
    data = load_json_file(secrets_path)
    return data if isinstance(data, dict) else {}

def abbreviate(n: int) -> str:
    if n < 1000:
        return str(n)
    for div, suf in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "k")):
        if n >= div:
            val = n / div
            return f"{int(val)}{suf}" if val >= 10 else f"{val:.1f}{suf}".rstrip(".0")
    return str(n)

def truncate_text(text: str, max_chars: int) -> str:
    return text if len(text) <= max_chars else text[: max_chars - 1] + "…"
