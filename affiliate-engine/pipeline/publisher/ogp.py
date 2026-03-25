"""Auto-generate OGP (Open Graph Protocol) images for articles.

Creates simple, branded social sharing images using Pillow.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from pipeline.models import Article

logger = logging.getLogger(__name__)

_WIDTH = 1200
_HEIGHT = 630
_BG_COLOR = (24, 24, 27)  # zinc-900
_TEXT_COLOR = (250, 250, 250)
_ACCENT_COLOR = (59, 130, 246)  # blue-500


def generate_ogp_image(article: Article, *, output_dir: Path) -> Path:
    """Generate an OGP image for an article."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / f"{article.meta.slug}.png"

    img = Image.new("RGB", (_WIDTH, _HEIGHT), _BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Accent bar at top
    draw.rectangle([(0, 0), (_WIDTH, 6)], fill=_ACCENT_COLOR)

    # Load available font (fallback to default)
    title_font = _load_font(size=48)
    sub_font = _load_font(size=24)

    # Title text (word-wrapped)
    title = article.meta.title
    _draw_wrapped_text(draw, title, title_font, x=80, y=160, max_width=_WIDTH - 160)

    # Keyword badge
    draw.rounded_rectangle(
        [(80, _HEIGHT - 120), (80 + len(article.meta.keyword) * 28 + 40, _HEIGHT - 70)],
        radius=8,
        fill=_ACCENT_COLOR,
    )
    draw.text((100, _HEIGHT - 114), article.meta.keyword, fill=_TEXT_COLOR, font=sub_font)

    img.save(filepath, "PNG", optimize=True)
    logger.info("Generated OGP image: %s", filepath)
    return filepath


def _draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    x: int,
    y: int,
    max_width: int,
) -> None:
    """Draw text with word wrapping."""
    chars_per_line = max(1, max_width // 48)
    lines: list[str] = []
    current = ""

    for char in text:
        current += char
        if len(current) >= chars_per_line:
            lines.append(current)
            current = ""
    if current:
        lines.append(current)

    for i, line in enumerate(lines[:3]):
        if i == 2 and len(lines) > 3:
            line = line[:-1] + "…"
        draw.text((x, y + i * 64), line, fill=_TEXT_COLOR, font=font)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Attempt to load a Japanese-capable font, fall back to default."""
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue

    return ImageFont.load_default()
