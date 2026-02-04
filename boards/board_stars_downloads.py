from typing import List, Tuple, Dict
from pathlib import Path
from html import escape as esc
from core.utils import abbreviate, truncate_text

# --- rendering ---------------------------------------------------------------
STAR_PATH = (
    "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 "
    "2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l."
    "72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z"
)

def get_badge_style(n: int) -> Tuple[str, str]:
    if n >= 10_000:
        return "#2ea44f", "#ffffff"
    if n >= 1_000:
        return "#d29922", "#ffffff"
    return "#6e7681", "#ffffff"

def generate_svg_content(username: str, rows: List[Tuple[str, int, int]], options: Dict) -> str:
    width = 800
    row_h, row_gap = 40, 4
    header_h, footer_h = 80, 60
    padding_x = 20
    
    # Options
    theme = options.get("theme", "dark")
    dark_mode = str(theme).lower() == "dark"
    show_stars = options.get("show_stars", True)
    
    # Calculate height based on rows
    height = header_h + (len(rows) * (row_h + row_gap)) + footer_h

    if dark_mode:
        bg, fg, muted, row_bg, border = "#0d1117", "#e6edf3", "#8b949e", "#161b22", "#30363d"
    else:
        bg, fg, muted, row_bg, border = "#ffffff", "#24292f", "#57606a", "#f6f8fa", "#d0d7de"

    font_family = "Segoe UI, Helvetica, Arial, sans-serif"
    lines: List[str] = []
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">'
    )
    lines.append(f'<rect width="{width}" height="{height}" rx="10" fill="{bg}" stroke="{border}" stroke-width="1" />')

    # Header: left profile, right repo count
    lines.append(f'<g transform="translate({padding_x}, 35)">')
    lines.append(f'<text fill="{fg}" font-size="20" font-family="{font_family}" font-weight="600">@{esc(username)}</text>')
    lines.append(f'<text y="25" fill="{muted}" font-size="14" font-family="{font_family}">Repo Statistics</text>')
    lines.append("</g>")
    lines.append(f'<text x="{width - padding_x}" y="30" fill="{muted}" font-size="12" font-family="{font_family}" text-anchor="end">{len(rows)} Repositories</text>')

    y_cursor = header_h
    badge_w, badge_h = 80, 24

    for name, downloads, stars in rows:
        bg_badge, fg_badge = get_badge_style(downloads)

        # Row background
        lines.append(f'<rect x="{padding_x}" y="{y_cursor}" width="{width - padding_x*2}" height="{row_h}" rx="6" fill="{row_bg}"/>')

        # Repo name
        lines.append(
            f'<text x="{padding_x + 12}" y="{y_cursor + 25}" fill="{fg}" font-size="14" font-family="{font_family}" font-weight="500">{esc(truncate_text(name, 45))}</text>'
        )

        # Stars group (if enabled)
        if show_stars:
            star_x = width - 210
            lines.append(f'<g transform="translate({star_x}, {y_cursor + 12})">')
            lines.append(f'<path d="{STAR_PATH}" fill="{muted}"/>')
            lines.append(f'<text x="20" y="13" fill="{muted}" font-size="13" font-family="{font_family}">{abbreviate(stars)}</text>')
            lines.append("</g>")

        # Downloads badge
        bx, by = width - padding_x - badge_w - 10, y_cursor + (row_h - badge_h) / 2
        lines.append(f'<rect x="{bx}" y="{by}" width="{badge_w}" height="{badge_h}" rx="12" fill="{bg_badge}"/>')
        lines.append(
            f'<text x="{bx + badge_w/2}" y="{by + 16}" fill="{fg_badge}" font-size="12" font-weight="bold" font-family="{font_family}" text-anchor="middle">{abbreviate(downloads)}</text>'
        )

        y_cursor += row_h + row_gap

    # Footer
    total_dl = sum(r[1] for r in rows)
    total_stars = sum(r[2] for r in rows)

    footer_x_base = width - 210
    footer_y = y_cursor + 30

    lines.append(f'<line x1="{padding_x}" y1="{y_cursor + 5}" x2="{width - padding_x}" y2="{y_cursor + 5}" stroke="{border}" />')
    lines.append(f'<text x="{padding_x}" y="{footer_y + 10}" fill="{fg}" font-size="16" font-family="{font_family}" font-weight="600">TOTAL</text>')

    if show_stars:
        lines.append(f'<g transform="translate({footer_x_base}, {footer_y - 4})">')
        lines.append(f'<path d="{STAR_PATH}" fill="{muted}"/>')
        lines.append(f'<text x="22" y="14" fill="{muted}" font-size="14" font-family="{font_family}">{abbreviate(total_stars)}</text>')
        lines.append("</g>")

    lines.append(
        f'<text x="{width - padding_x - 30}" y="{footer_y + 10}" fill="#0969da" font-size="18" font-family="{font_family}" font-weight="bold" text-anchor="end">{abbreviate(total_dl)}</text>'
    )

    lines.append("</svg>")
    return "\n".join(lines)

def render_svg(username: str, rows: List[Tuple[str, int, int]], out_path: Path, options: Dict) -> None:
    svg_content = generate_svg_content(username, rows, options)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        f.write(svg_content)
