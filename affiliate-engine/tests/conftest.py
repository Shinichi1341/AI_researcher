"""Shared test fixtures."""

from __future__ import annotations

import pytest

from pipeline.models import (
    Platform,
    Product,
    ProductPrice,
    ProductSpec,
)


@pytest.fixture
def sample_products() -> list[Product]:
    """A set of sample products for testing."""
    return [
        Product(
            id="amazon_B001",
            title="テスト加湿器 Pro 2024年モデル",
            platform=Platform.AMAZON,
            asin="B001",
            brand="テストブランド",
            category="家電",
            description="超音波式加湿器。容量4L、適用面積20畳。",
            prices=[
                ProductPrice(
                    platform=Platform.AMAZON,
                    price=8980,
                    url="https://amazon.co.jp/dp/B001",
                    affiliate_url="https://amazon.co.jp/dp/B001?tag=test-22",
                )
            ],
            specs=[
                ProductSpec(name="容量", value="4", unit="L"),
                ProductSpec(name="適用面積", value="20", unit="畳"),
                ProductSpec(name="消費電力", value="25", unit="W"),
            ],
            review_count=1250,
            review_rating=4.3,
            affiliate_url="https://amazon.co.jp/dp/B001?tag=test-22",
        ),
        Product(
            id="rakuten_R002",
            title="おしゃれ加湿器 Slim タワー型",
            platform=Platform.RAKUTEN,
            brand="スリムテック",
            category="家電",
            description="スリムなタワー型加湿器。容量3L、静音設計。",
            prices=[
                ProductPrice(
                    platform=Platform.RAKUTEN,
                    price=6480,
                    url="https://item.rakuten.co.jp/shop/r002",
                    affiliate_url="https://hb.afl.rakuten.co.jp/hgc/xxx/r002",
                )
            ],
            specs=[
                ProductSpec(name="容量", value="3", unit="L"),
                ProductSpec(name="適用面積", value="14", unit="畳"),
                ProductSpec(name="消費電力", value="18", unit="W"),
                ProductSpec(name="騒音レベル", value="26", unit="dB"),
            ],
            review_count=340,
            review_rating=4.1,
            affiliate_url="https://hb.afl.rakuten.co.jp/hgc/xxx/r002",
        ),
        Product(
            id="amazon_B003",
            title="ハイブリッド加湿器 HB-500",
            platform=Platform.AMAZON,
            asin="B003",
            brand="ハイブリテック",
            category="家電",
            description="気化式+超音波のハイブリッド。容量6L。",
            prices=[
                ProductPrice(
                    platform=Platform.AMAZON,
                    price=15800,
                    url="https://amazon.co.jp/dp/B003",
                    affiliate_url="https://amazon.co.jp/dp/B003?tag=test-22",
                )
            ],
            specs=[
                ProductSpec(name="容量", value="6", unit="L"),
                ProductSpec(name="適用面積", value="30", unit="畳"),
                ProductSpec(name="消費電力", value="35", unit="W"),
            ],
            review_count=89,
            review_rating=4.6,
            affiliate_url="https://amazon.co.jp/dp/B003?tag=test-22",
        ),
    ]
