"""Publish articles as Markdown files with Astro-compatible frontmatter."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from pipeline.models import Article

logger = logging.getLogger(__name__)


def publish_article(article: Article, *, output_dir: Path) -> Path:
    """Write an article as a Markdown file with YAML frontmatter.

    Returns the path to the written file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / f"{article.meta.slug}.md"

    frontmatter = {
        "title": article.meta.title,
        "description": article.meta.description,
        "slug": article.meta.slug,
        "articleType": article.meta.article_type.value,
        "keyword": article.meta.keyword,
        "category": article.meta.category,
        "products": article.meta.products,
        "createdAt": article.meta.created_at.isoformat(),
        "updatedAt": article.meta.updated_at.isoformat(),
    }

    yaml_str = yaml.dump(
        frontmatter,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )

    content = f"---\n{yaml_str}---\n\n{article.content}\n"

    filepath.write_text(content, encoding="utf-8")
    logger.info("Published article: %s", filepath)
    return filepath


def publish_batch(articles: list[Article], *, output_dir: Path) -> list[Path]:
    """Publish multiple articles and return their file paths."""
    return [publish_article(a, output_dir=output_dir) for a in articles]
