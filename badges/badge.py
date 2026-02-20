"""
Shields.io-style badge renderer.
Generates a two-part pill SVG: [icon label | value]

Supported badge_type values:
  - stars         (repo-level)
  - downloads     (repo-level)
  - followers     (user-level)
  - watchers      (repo-level, uses subscribers_count)
  - workflow_status (repo-level, status text + status-driven color)
"""
from typing import Dict, Union
from pathlib import Path
from html import escape as esc
from core.utils import abbreviate

# ── SVG icon paths (16×16 viewbox) ──────────────────────────────────────────

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
FOLLOWERS_ICON = (
    "M2 5.5a3.5 3.5 0 1 1 5.898 2.549 5.508 5.508 0 0 1 3.034 4.084.75.75 0 1 1"
    "-1.482.235 4.001 4.001 0 0 0-6.9 0 .75.75 0 0 1-1.482-.236A5.507 5.507 0 0 1"
    " 4.102 8.05 3.493 3.493 0 0 1 2 5.5ZM11 4a3.001 3.001 0 0 1 2.22 5.018 5.01"
    " 5.01 0 0 1 2.56 3.012.749.749 0 0 1-.885.954.752.752 0 0 1-.549-.514 3.507"
    " 3.507 0 0 0-2.522-2.372.75.75 0 0 1-.574-.73v-.352a.75.75 0 0 1 .416-.672"
    "A1.5 1.5 0 0 0 11 4Zm-5.5-.5a2 2 0 1 0-.001 3.999A2 2 0 0 0 5.5 3.5Z"
)
EYE_ICON = (
    "M8 2c1.981 0 3.671.992 4.933 2.078 1.27 1.091 2.187 2.345 2.637 3.023a1.62"
    " 1.62 0 0 1 0 1.798c-.45.678-1.367 1.932-2.637 3.023C11.671 13.008 9.981 14"
    " 8 14c-1.981 0-3.671-.992-4.933-2.078C1.797 10.831.88 9.577.43 8.899a1.62"
    " 1.62 0 0 1 0-1.798c.45-.678 1.367-1.932 2.637-3.023C4.329 2.992 6.019 2 8"
    " 2ZM1.679 7.932a.12.12 0 0 0 0 .136c.411.622 1.241 1.75 2.366 2.717C5.176"
    " 11.758 6.527 12.5 8 12.5c1.473 0 2.825-.742 3.955-1.715 1.124-.967 1.954"
    "-2.096 2.366-2.717a.12.12 0 0 0 0-.136c-.412-.621-1.242-1.75-2.366-2.717C10"
    ".824 4.242 9.473 3.5 8 3.5c-1.473 0-2.824.742-3.955 1.715-1.124.967-1.954"
    " 2.096-2.366 2.717ZM8 10a2 2 0 1 1-.001-3.999A2 2 0 0 1 8 10Z"
)
WORKFLOW_ICON = (
    "M0 1.75C0 .784.784 0 1.75 0h12.5C15.216 0 16 .784 16 1.75v12.5A1.75 1.75"
    " 0 0 1 14.25 16H1.75A1.75 1.75 0 0 1 0 14.25Zm1.75-.25a.25.25 0 0 0-.25"
    ".25v12.5c0 .138.112.25.25.25h12.5a.25.25 0 0 0 .25-.25V1.75a.25.25 0 0 0"
    "-.25-.25Zm9.22 3.72a.749.749 0 0 1 0 1.06L7.28 9.97a.749.749 0 0 1-1.06 0"
    "L4.47 8.22a.749.749 0 1 1 1.06-1.06l1.22 1.22 3.16-3.16a.749.749 0 0 1"
    " 1.06 0Z"
)
LICENSE_ICON = (
    "M8.75.75V2h.985c.304 0 .603.08.867.231l1.29.736c.038.022.08.033.124.033h2.234"
    "a.75.75 0 0 1 0 1.5h-.427l2.111 4.692a.75.75 0 0 1-.154.838l-.53-.53.529.531"
    "-.001.002-.002.002-.006.006-.006.005-.01.01a3.2 3.2 0 0 1-.106.086 2 2 0 0 1"
    "-.395.199c-.406.158-.936.24-1.558.24-.622 0-1.152-.082-1.558-.24a2 2 0 0 1-.395"
    "-.2 3 3 0 0 1-.106-.085l-.01-.01-.006-.005-.005-.006-.002-.002-.001-.002-.53.53"
    ".53-.53a.75.75 0 0 1-.154-.838L13.823 4.5h-.427a.6.6 0 0 1-.187-.03l-7.209"
    " 7.21-.53-.53a.75.75 0 0 1-1.06 0l-.53.53-.001-.002-.002-.002-.006-.006-.006"
    "-.005-.01-.01a2 2 0 0 1-.106-.086 2 2 0 0 1-.395-.199c-.406-.158-.936-.24-1.558"
    "-.24-.622 0-1.152.082-1.558.24a2 2 0 0 1-.395.2 3 3 0 0 1-.106.085l-.01.01"
    "-.006.005-.005.006-.002.002-.001.002L.22 10.94a.75.75 0 0 1-.154-.838L2.178"
    " 5.5h-.427a.75.75 0 0 1 0-1.5h2.234a.25.25 0 0 0 .124-.033l1.29-.736A1.75"
    " 1.75 0 0 1 6.265 3H7.25V.75a.75.75 0 0 1 1.5 0Z"
)

# Badge type → (label text, icon path)
BADGE_CONFIG = {
    "stars":           ("GitHub stars",    STAR_ICON),
    "downloads":       ("GitHub downloads", DOWNLOAD_ICON),
    "followers":       ("GitHub followers", FOLLOWERS_ICON),
    "watchers":        ("GitHub watchers",  EYE_ICON),
    "workflow_status": ("build",            WORKFLOW_ICON),
    "license":         ("license",          LICENSE_ICON),
}


def _text_width(text: str, font_size: float = 11) -> float:
    """Rough character-width estimate for sans-serif at given size."""
    return len(text) * font_size * 0.56


def generate_badge_svg(
    username: str,
    repo: str,
    value: Union[int, str],
    options: Dict,
) -> str:
    """
    Render a Shields.io-style pill badge.

    For numeric badges (stars, downloads, followers, watchers):
        value is an int → abbreviated automatically.
    For workflow_status:
        value is a string like "passing", "failed", etc.
        The color is driven by the status, not by user's `color` option.
    """
    badge_type = options.get("badge_type", "stars")
    color = options.get("color", "#2ea44f")
    label_color = options.get("label_color", "#555")
    text_style = options.get("text_style", "normal")

    # Look up label & icon
    label_text, icon_path = BADGE_CONFIG.get(badge_type, ("badge", STAR_ICON))
    # Override label for workflow if a workflow file is specified
    if badge_type == "workflow_status":
        wf = options.get("workflow", "")
        if wf:
            label_text = wf.replace(".yml", "").replace(".yaml", "")

    # Value text
    if isinstance(value, int):
        value_text = abbreviate(value)
    else:
        value_text = str(value)

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
    # Ensure minimum value width
    value_w = max(value_w, 32)
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
        f'{esc(label_text)}</text>'
    )

    # Value text (centered in value half)
    val_text_x = label_w + value_w / 2
    svg += (
        f'<text x="{val_text_x:.0f}" y="{text_y:.1f}" fill="#fff" '
        f'font-family="Verdana,Geneva,DejaVu Sans,sans-serif" '
        f'font-size="{font_size}" font-weight="{font_weight}" '
        f'font-style="{font_style_attr}" text-anchor="middle">'
        f'{esc(value_text)}</text>'
    )

    svg += '</svg>'
    return svg


def render_badge_svg(
    username: str,
    repo: str,
    value: Union[int, str],
    out_path: Path,
    options: Dict,
) -> None:
    """Write badge SVG to file."""
    content = generate_badge_svg(username, repo, value, options)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        f.write(content)
