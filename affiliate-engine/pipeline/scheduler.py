"""Automated review processing scheduler.

Picks one unprocessed review from reviews/, runs the full pipeline
(research + X posts + Note article), saves results, and marks the
review as processed.

If no unprocessed review exists, falls back to auto mode: picks a
theme from data/auto_themes.json and generates content automatically.

Usage:
    python -m pipeline.scheduler              # process 1 review (or auto)
    python -m pipeline.scheduler --dry-run    # show what would be processed
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

from pipeline.config import PROJECT_ROOT, get_settings
from pipeline.notify import notify
from pipeline.research import (
    Mode,
    build_unified_output,
    generate_note_article,
    generate_x_posts,
    research_theme,
    save_note_article,
    save_research,
    save_unified_json,
    save_x_posts,
)

logger = logging.getLogger(__name__)

REVIEWS_DIR = PROJECT_ROOT / "reviews"
PROCESSED_DIR = REVIEWS_DIR / "processed"
PROCESSED_JSON = PROJECT_ROOT / "data" / "processed_reviews.json"
AUTO_THEMES_JSON = PROJECT_ROOT / "data" / "auto_themes.json"
OUTPUT_DIR = PROJECT_ROOT / "data" / "research"


# ---------------------------------------------------------------------------
# Frontmatter parser
# ---------------------------------------------------------------------------
def parse_review_file(path: Path) -> tuple[dict, str]:
    """Parse a review Markdown file into (frontmatter_dict, body_text).

    Handles YAML-like frontmatter between --- delimiters.
    """
    text = path.read_text(encoding="utf-8")
    frontmatter: dict = {}
    body = text

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            # parts[0] is empty, parts[1] is frontmatter, parts[2] is body
            for line in parts[1].strip().splitlines():
                if ":" in line:
                    key, _, value = line.partition(":")
                    frontmatter[key.strip()] = value.strip()
            body = parts[2].strip()

    return frontmatter, body


# ---------------------------------------------------------------------------
# Processed tracking
# ---------------------------------------------------------------------------
def load_processed() -> list[str]:
    """Load list of already-processed review slugs."""
    if PROCESSED_JSON.exists():
        return json.loads(PROCESSED_JSON.read_text(encoding="utf-8"))
    return []


def save_processed(slugs: list[str]) -> None:
    """Save updated processed list."""
    PROCESSED_JSON.parent.mkdir(parents=True, exist_ok=True)
    PROCESSED_JSON.write_text(
        json.dumps(slugs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_slug(path: Path) -> str:
    """Get slug from filename (without extension)."""
    return path.stem


# ---------------------------------------------------------------------------
# File selection
# ---------------------------------------------------------------------------
def find_unprocessed_review() -> Path | None:
    """Find one unprocessed review file, oldest first."""
    processed = set(load_processed())

    candidates = []
    for md_file in sorted(REVIEWS_DIR.glob("*.md")):
        if md_file.name == "README.md":
            continue
        if get_slug(md_file) in processed:
            continue
        candidates.append(md_file)

    if not candidates:
        return None

    # Return the first (oldest by filename sort)
    return candidates[0]


# ---------------------------------------------------------------------------
# Mark as processed
# ---------------------------------------------------------------------------
def mark_processed(path: Path) -> None:
    """Move review to processed/ and update tracking JSON."""
    slug = get_slug(path)

    # Update JSON
    processed = load_processed()
    if slug not in processed:
        processed.append(slug)
        save_processed(processed)

    # Move file
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    dest = PROCESSED_DIR / path.name
    shutil.move(str(path), str(dest))
    logger.info("Moved %s → %s", path.name, dest)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def process_one_review(dry_run: bool = False) -> dict | None:
    """Process a single unprocessed review. Returns unified output dict or None."""
    review_path = find_unprocessed_review()

    if review_path is None:
        logger.info("未処理のレビューがありません")
        return None

    frontmatter, body = parse_review_file(review_path)
    keyword = frontmatter.get("keyword", review_path.stem)
    slug = get_slug(review_path)

    logger.info("処理対象: %s (keyword: %s)", review_path.name, keyword)

    if dry_run:
        print(f"[DRY RUN] 処理対象: {review_path.name}")
        print(f"  keyword: {keyword}")
        print(f"  rating:  {frontmatter.get('rating', 'N/A')}")
        print(f"  本文:    {body[:100]}...")
        return None

    settings = get_settings()
    if not settings.gemini_api_key:
        logger.error("GEMINI_API_KEY が設定されていません")
        return None

    # 1. Research (review mode)
    result = research_theme(
        keyword,
        gemini_api_key=settings.gemini_api_key,
        mode=Mode.REVIEW,
        user_review=body,
    )
    save_research(result, OUTPUT_DIR)

    # 2. X posts
    x_posts_md = generate_x_posts(
        result,
        gemini_api_key=settings.gemini_api_key,
    )
    save_x_posts(result.theme, x_posts_md, OUTPUT_DIR)

    # 3. Note article
    note_md = generate_note_article(
        result,
        gemini_api_key=settings.gemini_api_key,
    )
    save_note_article(result.theme, note_md, OUTPUT_DIR)

    # 4. Unified JSON
    unified = build_unified_output(result, x_posts_md, note_md)
    save_unified_json(unified, OUTPUT_DIR)

    # 5. Mark as processed
    mark_processed(review_path)

    # 6. Notify (Gmail / Slack)
    output_dict = unified.model_dump(mode="json")
    notify(output_dict)

    logger.info("✅ 完了: %s", keyword)
    return output_dict


# ---------------------------------------------------------------------------
# Auto mode fallback
# ---------------------------------------------------------------------------
def load_auto_themes() -> list[str]:
    """Load auto-research theme list."""
    if AUTO_THEMES_JSON.exists():
        return json.loads(AUTO_THEMES_JSON.read_text(encoding="utf-8"))
    return []


def save_auto_themes(themes: list[str]) -> None:
    """Save updated auto themes list."""
    AUTO_THEMES_JSON.write_text(
        json.dumps(themes, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Auto theme replenishment via Google Search Grounding
# ---------------------------------------------------------------------------
AUTO_REPLENISH_THRESHOLD = 3  # 残り何件以下で補充するか
AUTO_REPLENISH_COUNT = 5       # 1回の補充で追加する件数

REPLENISH_SYSTEM_PROMPT = """\
あなたはお酒メディアのトレンドリサーチャーです。
Google検索の最新情報を使って、今注目のお酒関連テーマを提案してください。

# 絶対ルール
- 日本市場向け（日本語で検索されるテーマ）
- 各テーマは「商品カテゴリ + 切り口」の形式にする
- 実在する商品名・ブランド名を使う
- 架空の商品は禁止
- アフィリエイト記事のネタとして使えるものだけ
"""

REPLENISH_USER_PROMPT = """\
以下の3カテゴリから、合計{count}件のテーマを提案してください。
各テーマは30文字以内で、検索キーワードとして自然な形にしてください。

## カテゴリ

### New Release（新商品・新作）
直近1ヶ月以内に発売/発表された新作のお酒。

### Market Trend（市場トレンド）
今検索されている話題。定価販売情報、コスパ比較、人気ランキングなど。

### Seasonal（季節もの）
今の季節（{month}月）に合ったお酒テーマ。飲み方・シーン提案を含む。

## 既存テーマ（重複禁止）
{existing_themes}

## 出力形式
以下の形式で{count}件出力してください。他の説明は不要。

[New Release] テーマ文
[Market Trend] テーマ文
[Seasonal] テーマ文
...
"""


def replenish_auto_themes(
    *,
    gemini_api_key: str,
    count: int = AUTO_REPLENISH_COUNT,
    model_name: str = "gemini-2.5-flash",
) -> list[str]:
    """Use Gemini with Google Search Grounding to find trending alcohol themes."""
    from google import genai
    from google.genai import types

    logger.info("🔍 テーマ自動補充開始（%d件）", count)

    existing = load_auto_themes()
    existing_str = "\n".join(f"- {t}" for t in existing) if existing else "（なし）"
    month = datetime.now().month

    client = genai.Client(api_key=gemini_api_key)

    response = client.models.generate_content(
        model=model_name,
        contents=REPLENISH_USER_PROMPT.format(
            count=count,
            month=month,
            existing_themes=existing_str,
        ),
        config=types.GenerateContentConfig(
            system_instruction=REPLENISH_SYSTEM_PROMPT,
            temperature=0.7,
            max_output_tokens=2048,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )

    raw = response.text.strip()
    logger.info("補充候補:\n%s", raw)

    # Parse output lines like "[New Release] テーマ文"
    new_themes = []
    existing_lower = {t.lower() for t in existing}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # Remove category tag if present
        if line.startswith("["):
            bracket_end = line.find("]")
            if bracket_end != -1:
                line = line[bracket_end + 1:].strip()
        # Remove leading bullets/numbers
        if line and line[0] in "-・0123456789.":
            line = line.lstrip("-・0123456789. ").strip()
        if not line:
            continue
        # Dedup check
        if line.lower() in existing_lower:
            logger.info("重複スキップ: %s", line)
            continue
        existing_lower.add(line.lower())
        new_themes.append(line)

    if new_themes:
        updated = existing + new_themes
        save_auto_themes(updated)
        logger.info("✅ %d件追加（合計%d件）", len(new_themes), len(updated))
    else:
        logger.warning("補充できるテーマがありませんでした")

    return new_themes


def ensure_auto_themes(*, gemini_api_key: str) -> None:
    """Check theme count and replenish if below threshold."""
    themes = load_auto_themes()
    if len(themes) >= AUTO_REPLENISH_THRESHOLD:
        return
    logger.info(
        "テーマ残数 %d（閾値 %d以下）→ 自動補充します",
        len(themes), AUTO_REPLENISH_THRESHOLD,
    )
    replenish_auto_themes(gemini_api_key=gemini_api_key)


def process_auto(dry_run: bool = False) -> dict | None:
    """Pick a theme from auto_themes.json and run auto-mode research."""
    settings = get_settings()

    # Replenish themes if running low
    if not dry_run and settings.gemini_api_key:
        ensure_auto_themes(gemini_api_key=settings.gemini_api_key)

    themes = load_auto_themes()
    if not themes:
        logger.info("auto_themes.json が空です。処理をスキップします")
        return None

    theme = themes[0]
    logger.info("[AUTO] テーマ: %s", theme)

    if dry_run:
        print(f"[DRY RUN / AUTO] テーマ: {theme}")
        print(f"  残りテーマ数: {len(themes) - 1}")
        return None

    if not settings.gemini_api_key:
        logger.error("GEMINI_API_KEY が設定されていません")
        return None

    # 1. Research (auto mode)
    result = research_theme(
        theme,
        gemini_api_key=settings.gemini_api_key,
        mode=Mode.AUTO,
    )
    save_research(result, OUTPUT_DIR)

    # 2. X posts
    x_posts_md = generate_x_posts(
        result,
        gemini_api_key=settings.gemini_api_key,
    )
    save_x_posts(result.theme, x_posts_md, OUTPUT_DIR)

    # 3. Note article
    note_md = generate_note_article(
        result,
        gemini_api_key=settings.gemini_api_key,
    )
    save_note_article(result.theme, note_md, OUTPUT_DIR)

    # 4. Unified JSON
    unified = build_unified_output(result, x_posts_md, note_md)
    save_unified_json(unified, OUTPUT_DIR)

    # 5. Remove used theme
    themes.pop(0)
    save_auto_themes(themes)

    # 6. Notify
    output_dict = unified.model_dump(mode="json")
    notify(output_dict)

    logger.info("✅ [AUTO] 完了: %s", theme)
    return output_dict


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="未処理レビュー → review モード / なければ auto モードで自動処理",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="実際には処理せず、対象を表示するだけ",
    )
    args = parser.parse_args()

    # Try review mode first, fall back to auto
    result = process_one_review(dry_run=args.dry_run)

    if result is None and not args.dry_run:
        # No unprocessed review → auto mode
        result = process_auto(dry_run=args.dry_run)
    elif result is None and args.dry_run:
        # dry-run: also show auto fallback
        if find_unprocessed_review() is None:
            process_auto(dry_run=True)

    if result and not args.dry_run:
        mode_label = result.get('mode', 'auto')
        print(f"\n✅ 処理完了 [{mode_label}]: {result['theme']}")
        print(f"📦 統合JSON に X投稿 3パターン + Note記事を格納済み")


if __name__ == "__main__":
    main()
