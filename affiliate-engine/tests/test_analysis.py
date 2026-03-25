"""Tests for the analysis module."""

import json
import tempfile
from datetime import date
from pathlib import Path

from pipeline.analysis.comparator import build_comparison
from pipeline.analysis.price_analyzer import (
    compute_price_stats,
    find_best_platform,
    record_prices,
)
from pipeline.models import (
    Platform,
    PriceHistory,
    PriceHistoryEntry,
    Product,
)


class TestComparator:
    def test_build_comparison_creates_axes(self, sample_products: list[Product]):
        result = build_comparison("加湿器 おすすめ", sample_products)
        assert result.keyword == "加湿器 おすすめ"
        assert len(result.products) == 3
        assert len(result.axes) > 0
        assert len(result.scores) == 3

    def test_price_axis_exists(self, sample_products: list[Product]):
        result = build_comparison("加湿器", sample_products)
        price_axes = [a for a in result.axes if a.axis_name == "最安値"]
        assert len(price_axes) == 1
        assert price_axes[0].best_product_id == "rakuten_R002"

    def test_shared_spec_axes(self, sample_products: list[Product]):
        result = build_comparison("加湿器", sample_products)
        spec_names = {a.axis_name for a in result.axes}
        # 容量, 適用面積, 消費電力 are shared by ≥2 products
        assert "容量" in spec_names
        assert "適用面積" in spec_names
        assert "消費電力" in spec_names
        # 騒音レベル is only on 1 product -> not included
        assert "騒音レベル" not in spec_names

    def test_empty_products(self):
        result = build_comparison("empty", [])
        assert result.products == []
        assert result.axes == []


class TestPriceAnalyzer:
    def test_record_prices_creates_files(self, sample_products: list[Product]):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            histories = record_prices(sample_products, data_dir=data_dir)
            assert len(histories) == 3

            # Check file was created
            files = list((data_dir / "price_history").glob("*.json"))
            assert len(files) == 3

    def test_no_duplicate_entries(self, sample_products: list[Product]):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            # Record twice
            record_prices(sample_products, data_dir=data_dir)
            histories = record_prices(sample_products, data_dir=data_dir)

            for h in histories:
                today_entries = [e for e in h.entries if e.date == date.today()]
                platforms = [e.platform for e in today_entries]
                assert len(platforms) == len(set(platforms)), "Duplicate entry detected"

    def test_compute_price_stats(self):
        history = PriceHistory(
            product_id="test",
            product_title="Test Product",
            entries=[
                PriceHistoryEntry(date=date(2025, 1, 1), platform=Platform.AMAZON, price=1000),
                PriceHistoryEntry(date=date(2025, 1, 2), platform=Platform.AMAZON, price=900),
                PriceHistoryEntry(date=date(2025, 1, 3), platform=Platform.AMAZON, price=950),
            ],
        )
        stats = compute_price_stats(history)
        assert stats["amazon"]["current"] == 950
        assert stats["amazon"]["min"] == 900
        assert stats["amazon"]["max"] == 1000
        assert stats["amazon"]["avg"] == 950
        assert stats["amazon"]["change"] == 50
        assert stats["amazon"]["change_pct"] == 5.6

    def test_find_best_platform(self):
        history = PriceHistory(
            product_id="test",
            product_title="Test",
            entries=[
                PriceHistoryEntry(date=date(2025, 1, 1), platform=Platform.AMAZON, price=1000),
                PriceHistoryEntry(date=date(2025, 1, 1), platform=Platform.RAKUTEN, price=900),
            ],
        )
        best = find_best_platform(history)
        assert best == Platform.RAKUTEN
