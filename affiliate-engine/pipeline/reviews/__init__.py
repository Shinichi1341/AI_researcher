"""Review memo reader and processor.

Reads user-written review memos from the reviews/ directory,
tracks which have been processed, and provides structured data
for the enrichment pipeline.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ReviewMemo:
    """A user-written review memo parsed from Markdown."""

    filepath: Path
    keyword: str
    body: str
    category: str = "お酒"
    rating: float | None = None
    filename: str = ""

    def __post_init__(self) -> None:
        self.filename = self.filepath.stem


def read_review_memos(reviews_dir: Path) -> list[ReviewMemo]:
    """Read all Markdown review memos from the reviews directory."""
    if not reviews_dir.exists():
        return []

    memos: list[ReviewMemo] = []

    for md_file in sorted(reviews_dir.glob("*.md")):
        if md_file.name == "README.md":
            continue

        try:
            memo = _parse_memo(md_file)
            if memo:
                memos.append(memo)
        except Exception:
            logger.warning("Failed to parse review memo: %s", md_file.name)

    return memos


def get_unprocessed_memos(
    memos: list[ReviewMemo],
    data_dir: Path,
) -> list[ReviewMemo]:
    """Filter out memos that have already been processed."""
    processed = _load_processed(data_dir)
    return [m for m in memos if m.filename not in processed]


def mark_as_processed(filename: str, data_dir: Path) -> None:
    """Record a memo as processed so it won't be re-processed."""
    processed = _load_processed(data_dir)
    processed.add(filename)
    _save_processed(processed, data_dir)


def _parse_memo(filepath: Path) -> ReviewMemo | None:
    """Parse a single Markdown memo with YAML frontmatter."""
    text = filepath.read_text(encoding="utf-8").strip()

    if not text.startswith("---"):
        return None

    parts = text.split("---", 2)
    if len(parts) < 3:
        return None

    frontmatter = yaml.safe_load(parts[1])
    if not frontmatter or "keyword" not in frontmatter:
        return None

    body = parts[2].strip()
    if not body:
        return None

    return ReviewMemo(
        filepath=filepath,
        keyword=frontmatter["keyword"],
        body=body,
        category=frontmatter.get("category", "お酒"),
        rating=float(frontmatter["rating"]) if "rating" in frontmatter else None,
    )


def _load_processed(data_dir: Path) -> set[str]:
    filepath = data_dir / "processed_reviews.json"
    if filepath.exists():
        try:
            return set(json.loads(filepath.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def _save_processed(processed: set[str], data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    filepath = data_dir / "processed_reviews.json"
    filepath.write_text(
        json.dumps(sorted(processed), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
