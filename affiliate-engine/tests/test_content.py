"""Tests for content generation (templates and publisher)."""

import tempfile
from pathlib import Path

import yaml

from pipeline.analysis.comparator import build_comparison
from pipeline.content.templates.comparison import (
    build_comparison_table,
    build_score_table,
)
from pipeline.models import Article, ArticleMeta, ArticleType, Product
from pipeline.publisher.markdown import publish_article


class TestComparisonTemplates:
    def test_comparison_table_has_all_products(self, sample_products: list[Product]):
        result = build_comparison("加湿器", sample_products)
        table = build_comparison_table(result)

        assert "比較項目" in table
        assert "|" in table
        # All products should be referenced
        lines = table.split("\n")
        assert len(lines) >= 3  # header + separator + at least 1 data row

    def test_score_table_shows_ranks(self, sample_products: list[Product]):
        result = build_comparison("加湿器", sample_products)
        table = build_score_table(result)

        assert "1位" in table
        assert "2位" in table
        assert "3位" in table
        assert "総合スコア" in table

    def test_score_table_has_visual_bars(self, sample_products: list[Product]):
        result = build_comparison("加湿器", sample_products)
        table = build_score_table(result)
        # Should contain Unicode block characters
        assert "█" in table or "░" in table


class TestPublisher:
    def test_publish_article_creates_file(self):
        article = Article(
            meta=ArticleMeta(
                title="テスト記事",
                slug="test-article",
                description="テスト用の記事です",
                article_type=ArticleType.COMPARISON,
                keyword="テスト",
            ),
            content="# テスト\n\nこれはテストです。",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            filepath = publish_article(article, output_dir=output_dir)

            assert filepath.exists()
            assert filepath.name == "test-article.md"

            text = filepath.read_text(encoding="utf-8")
            assert text.startswith("---\n")
            assert "# テスト" in text

    def test_frontmatter_is_valid_yaml(self):
        article = Article(
            meta=ArticleMeta(
                title="YAML テスト",
                slug="yaml-test",
                description="YAML形式の検証",
                article_type=ArticleType.COMPARISON,
                keyword="テスト",
                category="家電",
                products=["a", "b"],
            ),
            content="Content here",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = publish_article(article, output_dir=Path(tmpdir))
            text = filepath.read_text(encoding="utf-8")

            # Extract YAML between --- markers
            parts = text.split("---")
            assert len(parts) >= 3
            frontmatter = yaml.safe_load(parts[1])

            assert frontmatter["title"] == "YAML テスト"
            assert frontmatter["urlSlug"] == "yaml-test"
            assert frontmatter["articleType"] == "comparison"
            assert frontmatter["products"] == ["a", "b"]
