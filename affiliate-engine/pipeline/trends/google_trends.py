"""Fetch trending keywords from Google Trends (Japan)."""

from __future__ import annotations

import logging
from datetime import datetime

from pytrends.request import TrendReq

from pipeline.models import TrendKeyword

logger = logging.getLogger(__name__)

# Product-related seed categories for affiliate relevance
_SEED_CATEGORIES = [
    "家電",
    "ガジェット",
    "PC周辺機器",
    "キッチン用品",
    "美容家電",
    "ゲーミング",
    "アウトドア",
    "文房具",
    "健康グッズ",
    "スマートホーム",
]


def fetch_trending_keywords(
    max_results: int = 20,
    seed_categories: list[str] | None = None,
) -> list[TrendKeyword]:
    """Discover currently trending product-related keywords in Japan.

    Uses Google Trends' related queries and trending searches
    filtered to product categories that have affiliate potential.
    """
    categories = seed_categories or _SEED_CATEGORIES
    keywords: list[TrendKeyword] = []
    seen: set[str] = set()

    try:
        pytrends = TrendReq(hl="ja-JP", tz=540)
    except Exception:
        logger.exception("Failed to initialize pytrends")
        return keywords

    for category in categories:
        try:
            pytrends.build_payload([category], geo="JP", timeframe="now 7-d")
            related = pytrends.related_queries()

            for query_type in ("top", "rising"):
                df = related.get(category, {}).get(query_type)
                if df is None or df.empty:
                    continue

                for _, row in df.iterrows():
                    kw = str(row.get("query", "")).strip()
                    if not kw or kw in seen:
                        continue
                    seen.add(kw)

                    value = row.get("value", 0)
                    score = float(value) if isinstance(value, (int, float)) else 0.0

                    keywords.append(
                        TrendKeyword(
                            keyword=kw,
                            category=category,
                            trend_score=score,
                            source="google_trends",
                            discovered_at=datetime.now(),
                        )
                    )

                    if len(keywords) >= max_results:
                        return _sort_by_score(keywords)

        except Exception:
            logger.warning("Failed to fetch trends for category: %s", category)
            continue

    return _sort_by_score(keywords)


def _sort_by_score(keywords: list[TrendKeyword]) -> list[TrendKeyword]:
    return sorted(keywords, key=lambda k: k.trend_score, reverse=True)
