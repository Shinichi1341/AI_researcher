"""Amazon Product Advertising API 5.0 client.

Implements the AWS Signature Version 4 signing required by PA-API 5.0.
Reference: https://webservices.amazon.co.jp/paapi5/documentation/
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

import httpx

from pipeline.config import AmazonConfig
from pipeline.models import Platform, Product, ProductPrice, ProductSpec

logger = logging.getLogger(__name__)

_PAAPI_HOST = "webservices.amazon.co.jp"
_PAAPI_PATH = "/paapi5/searchitems"
_SERVICE = "ProductAdvertisingAPI"


class AmazonClient:
    """Client for Amazon PA-API 5.0 with proper request signing."""

    def __init__(self, config: AmazonConfig) -> None:
        self._config = config
        self._http = httpx.Client(timeout=30.0)

    def search_products(self, keyword: str, max_results: int = 10) -> list[Product]:
        """Search products by keyword and return structured Product list."""
        if not self._config.is_configured:
            logger.warning("Amazon API not configured, skipping")
            return []

        payload = {
            "Keywords": keyword,
            "Resources": [
                "ItemInfo.Title",
                "ItemInfo.Features",
                "ItemInfo.ProductInfo",
                "ItemInfo.TechnicalInfo",
                "ItemInfo.ByLineInfo",
                "Offers.Listings.Price",
                "Images.Primary.Large",
                "CustomerReviews.Count",
                "CustomerReviews.StarRating",
            ],
            "ItemCount": min(max_results, 10),
            "PartnerTag": self._config.partner_tag,
            "PartnerType": "Associates",
            "Marketplace": self._config.marketplace,
        }

        headers = self._build_signed_headers(
            payload=json.dumps(payload),
            target="com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems",
        )

        try:
            resp = self._http.post(
                f"https://{_PAAPI_HOST}{_PAAPI_PATH}",
                content=json.dumps(payload),
                headers=headers,
            )
            resp.raise_for_status()
            return self._parse_response(resp.json())
        except httpx.HTTPStatusError:
            logger.exception("Amazon API request failed (HTTP %s)", resp.status_code)
            return []
        except Exception:
            logger.exception("Amazon API request failed")
            return []

    def _parse_response(self, data: dict) -> list[Product]:
        items = data.get("SearchResult", {}).get("Items", [])
        products: list[Product] = []

        for item in items:
            asin = item.get("ASIN", "")
            info = item.get("ItemInfo", {})
            offers = item.get("Offers", {})
            images = item.get("Images", {})
            reviews = item.get("CustomerReviews", {})

            # Extract price
            prices: list[ProductPrice] = []
            for listing in offers.get("Listings", []):
                price_info = listing.get("Price", {})
                amount = price_info.get("Amount")
                if amount is not None:
                    prices.append(
                        ProductPrice(
                            platform=Platform.AMAZON,
                            price=int(float(amount)),
                            url=item.get("DetailPageURL", ""),
                            affiliate_url=item.get("DetailPageURL", ""),
                        )
                    )

            # Extract specs from features
            specs: list[ProductSpec] = []
            features = info.get("Features", {}).get("DisplayValues", [])
            for feat in features:
                if ":" in feat:
                    name, value = feat.split(":", 1)
                    specs.append(ProductSpec(name=name.strip(), value=value.strip()))

            title_info = info.get("Title", {})
            brand_info = info.get("ByLineInfo", {}).get("Brand", {})
            image_info = images.get("Primary", {}).get("Large", {})
            rating = reviews.get("StarRating", {})
            count = reviews.get("Count", 0)

            products.append(
                Product(
                    id=f"amazon_{asin}",
                    title=title_info.get("DisplayValue", ""),
                    platform=Platform.AMAZON,
                    asin=asin,
                    brand=brand_info.get("DisplayValue", ""),
                    image_url=image_info.get("URL", ""),
                    prices=prices,
                    specs=specs,
                    review_count=count if isinstance(count, int) else 0,
                    review_rating=float(rating.get("Value", 0.0))
                    if isinstance(rating, dict)
                    else 0.0,
                    affiliate_url=item.get("DetailPageURL", ""),
                )
            )

        return products

    # ------------------------------------------------------------------
    # AWS Signature V4 signing
    # ------------------------------------------------------------------
    def _build_signed_headers(self, payload: str, target: str) -> dict[str, str]:
        now = datetime.now(timezone.utc)
        datestamp = now.strftime("%Y%m%d")
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")

        credential_scope = f"{datestamp}/{self._config.region}/{_SERVICE}/aws4_request"
        signed_headers = "content-encoding;content-type;host;x-amz-date;x-amz-target"

        headers = {
            "content-encoding": "amz-1.0",
            "content-type": "application/json; charset=utf-8",
            "host": _PAAPI_HOST,
            "x-amz-date": amz_date,
            "x-amz-target": target,
        }

        canonical_headers = "".join(f"{k}:{v}\n" for k, v in sorted(headers.items()))
        payload_hash = hashlib.sha256(payload.encode()).hexdigest()

        canonical_request = "\n".join([
            "POST",
            _PAAPI_PATH,
            "",
            canonical_headers,
            signed_headers,
            payload_hash,
        ])

        string_to_sign = "\n".join([
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ])

        signing_key = self._get_signing_key(datestamp)
        signature = hmac.new(
            signing_key, string_to_sign.encode(), hashlib.sha256
        ).hexdigest()

        auth = (
            f"AWS4-HMAC-SHA256 Credential={self._config.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        headers["Authorization"] = auth
        return headers

    def _get_signing_key(self, datestamp: str) -> bytes:
        k_date = self._hmac_sign(
            f"AWS4{self._config.secret_key}".encode(), datestamp
        )
        k_region = self._hmac_sign(k_date, self._config.region)
        k_service = self._hmac_sign(k_region, _SERVICE)
        return self._hmac_sign(k_service, "aws4_request")

    @staticmethod
    def _hmac_sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode(), hashlib.sha256).digest()

    def close(self) -> None:
        self._http.close()
