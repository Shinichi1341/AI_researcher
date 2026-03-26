"""Tests for the review memo reader and enricher."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from pipeline.reviews import (
    ReviewMemo,
    get_unprocessed_memos,
    mark_as_processed,
    read_review_memos,
)
from pipeline.reviews.enricher import _build_review_article, _format_product_data
from pipeline.models import Platform, Product, ProductPrice


class TestReviewMemoReader:
    def test_reads_valid_memo(self, tmp_path: Path):
        memo_file = tmp_path / "test-gin.md"
        memo_file.write_text(
            "---\nkeyword: クラフトジン ROKU\ncategory: お酒\nrating: 4.0\n---\n"
            "柑橘系の香りがすごい。トニック割りが最高。\n",
            encoding="utf-8",
        )
        memos = read_review_memos(tmp_path)
        assert len(memos) == 1
        assert memos[0].keyword == "クラフトジン ROKU"
        assert memos[0].category == "お酒"
        assert memos[0].rating == 4.0
        assert "柑橘系" in memos[0].body

    def test_skips_readme(self, tmp_path: Path):
        (tmp_path / "README.md").write_text("# readme", encoding="utf-8")
        memos = read_review_memos(tmp_path)
        assert len(memos) == 0

    def test_skips_memo_without_keyword(self, tmp_path: Path):
        memo_file = tmp_path / "bad.md"
        memo_file.write_text("---\ncategory: お酒\n---\nsome body\n", encoding="utf-8")
        memos = read_review_memos(tmp_path)
        assert len(memos) == 0

    def test_skips_memo_without_body(self, tmp_path: Path):
        memo_file = tmp_path / "empty-body.md"
        memo_file.write_text("---\nkeyword: テスト\n---\n", encoding="utf-8")
        memos = read_review_memos(tmp_path)
        assert len(memos) == 0

    def test_default_category(self, tmp_path: Path):
        memo_file = tmp_path / "no-cat.md"
        memo_file.write_text(
            "---\nkeyword: ウイスキー 白州\n---\n美味しい。\n", encoding="utf-8"
        )
        memos = read_review_memos(tmp_path)
        assert memos[0].category == "お酒"

    def test_empty_directory(self, tmp_path: Path):
        memos = read_review_memos(tmp_path)
        assert memos == []

    def test_nonexistent_directory(self):
        memos = read_review_memos(Path("/nonexistent"))
        assert memos == []


class TestProcessedTracking:
    def test_unprocessed_detection(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        memo1 = ReviewMemo(filepath=Path("a.md"), keyword="gin", body="good", filename="a")
        memo2 = ReviewMemo(filepath=Path("b.md"), keyword="whisky", body="nice", filename="b")

        # Both should be unprocessed initially
        unprocessed = get_unprocessed_memos([memo1, memo2], data_dir)
        assert len(unprocessed) == 2

        # Mark one as processed
        mark_as_processed("a", data_dir)
        unprocessed = get_unprocessed_memos([memo1, memo2], data_dir)
        assert len(unprocessed) == 1
        assert unprocessed[0].filename == "b"

    def test_processed_file_persists(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        mark_as_processed("test-memo", data_dir)

        processed_file = data_dir / "processed_reviews.json"
        assert processed_file.exists()
        data = json.loads(processed_file.read_text(encoding="utf-8"))
        assert "test-memo" in data


class TestReviewArticleBuilder:
    def test_builds_article_with_user_review(self):
        memo = ReviewMemo(
            filepath=Path("test.md"),
            keyword="クラフトジン ROKU",
            body="柑橘系の香りがすごい。トニック割りが最高。",
            category="お酒",
            rating=4.0,
        )

        enriched = {
            "intro": "ROKUは、サントリーが手掛けるジャパニーズクラフトジンです。",
            "objective_data": [
                {"label": "容量", "value": "700ml"},
                {"label": "アルコール度数", "value": "47%"},
            ],
            "pairing_suggestions": ["チーズ盛り合わせ", "柑橘系サラダ"],
            "buying_guide": "Amazonでの購入が最安値の傾向があります。",
        }

        content = _build_review_article(memo=memo, enriched=enriched, products=[])

        # User's original review is preserved verbatim
        assert "柑橘系の香りがすごい。トニック割りが最高。" in content
        # Enriched data is present
        assert "ROKUは、サントリー" in content
        assert "700ml" in content
        assert "47%" in content
        assert "チーズ盛り合わせ" in content
        # Rating is shown
        assert "4.0/5.0" in content
        # Disclaimer present
        assert "アフィリエイトプログラム" in content
        # Section headers
        assert "飲んでみた正直な感想" in content
        assert "基本データ" in content

    def test_builds_article_with_product_prices(self):
        memo = ReviewMemo(
            filepath=Path("t.md"),
            keyword="テスト",
            body="美味しい。",
        )

        products = [
            Product(
                id="amz_1",
                title="テスト商品",
                platform=Platform.AMAZON,
                prices=[
                    ProductPrice(
                        platform=Platform.AMAZON,
                        price=3980,
                        affiliate_url="https://amazon.co.jp/dp/X?tag=t-22",
                    )
                ],
            )
        ]

        content = _build_review_article(memo=memo, enriched={}, products=products)
        assert "¥3,980" in content
        assert "価格比較" in content
        assert "amazon.co.jp" in content

    def test_format_product_data_no_products(self):
        result = _format_product_data([])
        assert "商品データなし" in result
