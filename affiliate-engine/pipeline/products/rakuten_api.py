"""Rakuten Ichiba Product Search API client.

Reference: https://webservice.rakuten.co.jp/documentation/ichiba-item-search
"""

from __future__ import annotations

import logging

import httpx

from pipeline.config import RakutenConfig
from pipeline.models import Platform, Product, ProductPrice

logger = logging.getLogger(__name__)

_API_URL = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"


class RakutenClient:
    """Client for Rakuten Ichiba Item Search API."""

    def __init__(self, config: RakutenConfig) -> None:
        self._config = config
        self._http = httpx.Client(timeout=30.0)

    def search_products(self, keyword: str, max_results: int = 10) -> list[Product]:
        """Search Rakuten Ichiba by keyword."""
        if not self._config.is_configured:
            logger.warning("Rakuten API not configured, skipping")
            return []

        params = {
            "applicationId": self._config.app_id,
            "affiliateId": self._config.affiliate_id,
            "keyword": keyword,
            "hits": min(max_results, 30),
            "sort": "-reviewCount",
            "formatVersion": 2,
        }

        try:
            resp = self._http.get(_API_URL, params=params)
            resp.raise_for_status()
            return self._parse_response(resp.json())
        except httpx.HTTPStatusError:
            logger.exception("Rakuten API request failed (HTTP %s)", resp.status_code)
            return []
        except Exception:
            logger.exception("Rakuten API request failed")
            return []

    def _parse_response(self, data: dict) -> list[Product]:
        items = data.get("Items", [])
        products: list[Product] = []

        for item in items:
            item_code = item.get("itemCode", "")
            price = item.get("itemPrice", 0)
            affiliate_url = item.get("affiliateUrl", "") or item.get("itemUrl", "")

            images = item.get("mediumImageUrls", [])
            image_url = images[0] if images else ""

            prices = [
                ProductPrice(
                    platform=Platform.RAKUTEN,
                    price=int(price) if price else 0,
                    url=item.get("itemUrl", ""),
                    affiliate_url=affiliate_url,
                )
            ]

            products.append(
                Product(
                    id=f"rakuten_{item_code}",
                    title=item.get("itemName", ""),
                    platform=Platform.RAKUTEN,
                    category=item.get("genreId", ""),
                    brand=item.get("shopName", ""),
                    image_url=image_url,
                    description=item.get("itemCaption", ""),
                    prices=prices,
                    review_count=item.get("reviewCount", 0),
                    review_rating=float(item.get("reviewAverage", 0.0)),
                    affiliate_url=affiliate_url,
                )
            )

        return products

    def close(self) -> None:
        self._http.close()
