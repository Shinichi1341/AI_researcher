"""Pipeline orchestrator: end-to-end content generation workflow.

Usage:
    python -m pipeline.main              # Full pipeline
    python -m pipeline.main --dry-run    # Discover keywords only
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from pipeline.analysis.comparator import build_comparison
from pipeline.analysis.price_analyzer import record_prices
from pipeline.analysis.spec_extractor import batch_extract_specs
from pipeline.config import get_settings
from pipeline.content.generator import generate_comparison_article
from pipeline.models import Product, TrendKeyword
from pipeline.products.amazon_api import AmazonClient
from pipeline.products.rakuten_api import RakutenClient
from pipeline.publisher.markdown import publish_article
from pipeline.publisher.ogp import generate_ogp_image
from pipeline.trends.google_trends import fetch_trending_keywords
from pipeline.trends.seasonal import get_seasonal_keywords

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run_pipeline(*, dry_run: bool = False) -> None:
    """Execute the full content generation pipeline."""
    settings = get_settings()

    # ------------------------------------------------------------------
    # Step 1: Discover keywords
    # ------------------------------------------------------------------
    logger.info("Step 1/6: Discovering trending keywords...")
    keywords = _discover_keywords()

    if not keywords:
        logger.warning("No keywords discovered, exiting")
        return

    logger.info("Discovered %d keywords", len(keywords))
    _save_keywords(keywords, settings.data_dir)

    if dry_run:
        for kw in keywords:
            logger.info("  [%.0f] %s (%s)", kw.trend_score, kw.keyword, kw.source)
        return

    # ------------------------------------------------------------------
    # Step 2: Search products for each keyword
    # ------------------------------------------------------------------
    logger.info("Step 2/6: Searching products...")
    amazon = AmazonClient(settings.amazon)
    rakuten = RakutenClient(settings.rakuten)

    articles_generated = 0

    try:
        for kw in keywords[: settings.daily_article_limit]:
            logger.info("Processing keyword: %s", kw.keyword)

            products = _search_products(kw.keyword, amazon, rakuten)
            if len(products) < 2:
                logger.info("  Insufficient products (%d), skipping", len(products))
                continue

            # ----------------------------------------------------------
            # Step 3: Extract and normalize specs
            # ----------------------------------------------------------
            logger.info("Step 3/6: Extracting specs for %d products...", len(products))
            if settings.gemini_api_key:
                products = batch_extract_specs(
                    products, gemini_api_key=settings.gemini_api_key
                )

            # ----------------------------------------------------------
            # Step 4: Analyze and compare
            # ----------------------------------------------------------
            logger.info("Step 4/6: Building comparison...")
            comparison = build_comparison(kw.keyword, products)

            # Record price history
            comparison.price_histories = record_prices(
                products, data_dir=settings.data_dir
            )

            # ----------------------------------------------------------
            # Step 5: Generate article
            # ----------------------------------------------------------
            logger.info("Step 5/6: Generating article...")
            if not settings.gemini_api_key:
                logger.error("GEMINI_API_KEY not set, cannot generate articles")
                continue

            article = generate_comparison_article(
                comparison, gemini_api_key=settings.gemini_api_key
            )

            # ----------------------------------------------------------
            # Step 6: Publish
            # ----------------------------------------------------------
            logger.info("Step 6/6: Publishing...")
            publish_article(article, output_dir=settings.site_content_dir)
            generate_ogp_image(
                article, output_dir=settings.data_dir.parent / "site" / "public" / "ogp"
            )

            articles_generated += 1
            logger.info("Published: %s", article.meta.title)

    finally:
        amazon.close()
        rakuten.close()

    logger.info("Pipeline complete: %d articles generated", articles_generated)


def _discover_keywords() -> list[TrendKeyword]:
    """Merge Google Trends and seasonal keywords, deduplicate."""
    trending = fetch_trending_keywords(max_results=15)
    seasonal = get_seasonal_keywords()

    seen: set[str] = set()
    merged: list[TrendKeyword] = []

    for kw in trending + seasonal:
        if kw.keyword not in seen:
            seen.add(kw.keyword)
            merged.append(kw)

    return sorted(merged, key=lambda k: k.trend_score, reverse=True)


def _search_products(
    keyword: str,
    amazon: AmazonClient,
    rakuten: RakutenClient,
) -> list[Product]:
    """Search across platforms and merge results."""
    products: list[Product] = []
    products.extend(amazon.search_products(keyword, max_results=5))
    products.extend(rakuten.search_products(keyword, max_results=5))
    return products


def _save_keywords(keywords: list[TrendKeyword], data_dir: Path) -> None:
    """Persist discovered keywords for tracking."""
    data_dir.mkdir(parents=True, exist_ok=True)
    filepath = data_dir / "keywords.json"

    data = [kw.model_dump(mode="json") for kw in keywords]
    filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Affiliate Engine Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Only discover keywords")
    args = parser.parse_args()

    try:
        run_pipeline(dry_run=args.dry_run)
    except KeyboardInterrupt:
        logger.info("Interrupted")
        sys.exit(130)
    except Exception:
        logger.exception("Pipeline failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
