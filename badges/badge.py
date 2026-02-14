"""
Shields.io-style badge renderer for stars and downloads.
Generates a two-part pill SVG: [label | value]
"""
from typing import Dict
from pathlib import Path
from html import escape as esc
from core.utils import abbreviate

# SVG icon paths (16×16 viewbox)
STAR_ICON = (
    "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279"
    "l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75"
    " 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327"
    ".668A.75.75 0 0 1 8 .25Z"
)
DOWNLOAD_ICON = (
    "M2.75 14A1.75 1.75 0 0 1 1 12.25v-2.5a.75.75 0 0 1 1.5 0v2.5c0 .138.112"
    ".25.25.25h10.5a.25.25 0 0 0 .25-.25v-2.5a.75.75 0 0 1 1.5 0v2.5A1.75 1.75"
    " 0 0 1 13.25 14ZM7.25 7.689V2a.75.75 0 0 1 1.5 0v5.689l1.97-1.969a.749.749"
    " 0 1 1 1.06 1.06l-3.25 3.25a.749.749 0 0 1-1.06 0L4.22 6.78a.749.749 0 1 1"
    " 1.06-1.06l1.97 1.969Z"
)


def _text_width(text: str, font_size: float = 11) -> float:
    """Rough character-width estimate for sans-serif at given size."""
    return len(text) * font_size * 0.62


def generate_badge_svg(
    username: str,
    repo: str,
    value: int,
    options: Dict,
) -> str:
    """
    Render a Shields.io-style pill badge.

    options keys:
        badge_type  : "stars" | "downloads"
        color       : hex color for value half  (default "#2ea44f")
        label_color : hex color for label half  (default "#555")
        text_style  : "normal" | "bold" | "italic"  (default "normal")
    """
    badge_type = options.get("badge_type", "stars")
    color = options.get("color", "#2ea44f")
    label_color = options.get("label_color", "#555")
    text_style = options.get("text_style", "normal")

    # Determine label text & icon
    if badge_type == "downloads":
        label_text = f"GitHub downloads"
        icon_path = DOWNLOAD_ICON
    else:
        label_text = f"GitHub stars"
        icon_path = STAR_ICON

    value_text = abbreviate(value)

    # Font properties
    font_size = 11
    font_weight = "bold" if text_style == "bold" else "normal"
    font_style_attr = "italic" if text_style == "italic" else "normal"

    # Dimensions
    h = 20
    icon_w = 14
    icon_pad = 5
    pad = 6
    label_w = pad + icon_w + icon_pad + _text_width(label_text, font_size) + pad
    value_w = pad + _text_width(value_text, font_size) + pad
    total_w = label_w + value_w

    # Build SVG
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w:.0f}" height="{h}">'

    # Label half
    svg += f'<rect width="{label_w:.0f}" height="{h}" rx="3" fill="{esc(label_color)}"/>'
    # Value half
    svg += f'<rect x="{label_w:.0f}" width="{value_w:.0f}" height="{h}" rx="3" fill="{esc(color)}"/>'
    # Overlap fix (square join between halves)
    svg += f'<rect x="{label_w - 3:.0f}" width="6" height="{h}" fill="{esc(label_color)}"/>'
    svg += f'<rect x="{label_w:.0f}" width="3" height="{h}" fill="{esc(color)}"/>'

    # Icon
    icon_x = pad
    icon_y = (h - 14) / 2
    svg += (
        f'<g transform="translate({icon_x},{icon_y:.1f}) scale(0.875)">'
        f'<path d="{icon_path}" fill="#fff"/>'
        f'</g>'
    )

    # Label text
    text_x = pad + icon_w + icon_pad
    text_y = h / 2 + font_size * 0.36
    svg += (
        f'<text x="{text_x:.0f}" y="{text_y:.1f}" fill="#fff" '
        f'font-family="Verdana,Geneva,DejaVu Sans,sans-serif" '
        f'font-size="{font_size}" font-weight="{font_weight}" '
        f'font-style="{font_style_attr}">'
        f'{label_text}</text>'
    )

    # Value text (centered in value half)
    val_text_x = label_w + value_w / 2
    svg += (
        f'<text x="{val_text_x:.0f}" y="{text_y:.1f}" fill="#fff" '
        f'font-family="Verdana,Geneva,DejaVu Sans,sans-serif" '
        f'font-size="{font_size}" font-weight="{font_weight}" '
        f'font-style="{font_style_attr}" text-anchor="middle">'
        f'{value_text}</text>'
    )

    svg += '</svg>'
    return svg


def render_badge_svg(
    username: str,
    repo: str,
    value: int,
    out_path: Path,
    options: Dict,
) -> None:
    """Write badge SVG to file."""
    content = generate_badge_svg(username, repo, value, options)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        f.write(content)
