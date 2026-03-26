"""Pipeline orchestrator: end-to-end content generation workflow.

Usage:
    python -m pipeline.main                # Full pipeline (comparisons + reviews)
    python -m pipeline.main --dry-run      # Discover keywords only
    python -m pipeline.main --reviews-only # Process personal reviews only
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
from pipeline.config import PROJECT_ROOT, get_settings
from pipeline.content.generator import generate_comparison_article
from pipeline.models import Product, TrendKeyword
from pipeline.products.amazon_api import AmazonClient
from pipeline.products.rakuten_api import RakutenClient
from pipeline.publisher.markdown import publish_article
from pipeline.publisher.ogp import generate_ogp_image
from pipeline.reviews import get_unprocessed_memos, mark_as_processed, read_review_memos
from pipeline.reviews.enricher import enrich_review
from pipeline.trends.google_trends import fetch_trending_keywords
from pipeline.trends.seasonal import get_seasonal_keywords

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

REVIEWS_DIR = PROJECT_ROOT / "reviews"


def run_pipeline(*, dry_run: bool = False, reviews_only: bool = False) -> None:
    """Execute the full content generation pipeline."""
    settings = get_settings()
    amazon = AmazonClient(settings.amazon)
    rakuten = RakutenClient(settings.rakuten)
    articles_generated = 0

    try:
        # ==============================================================
        # Phase A: Process personal review memos
        # ==============================================================
        articles_generated += _process_reviews(
            amazon, rakuten, settings, dry_run=dry_run
        )

        if reviews_only:
            logger.info("Reviews-only mode: skipping comparison pipeline")
            return

        # ==============================================================
        # Phase B: Automated comparison articles
        # ==============================================================
        logger.info("=== Phase B: Comparison articles ===")

        # Step 1: Discover keywords
        logger.info("Step 1/6: Discovering trending keywords...")
        keywords = _discover_keywords()

        if not keywords:
            logger.warning("No keywords discovered")
        else:
            logger.info("Discovered %d keywords", len(keywords))
            _save_keywords(keywords, settings.data_dir)

            if dry_run:
                for kw in keywords:
                    logger.info("  [%.0f] %s (%s)", kw.trend_score, kw.keyword, kw.source)
            else:
                articles_generated += _process_comparisons(
                    keywords, amazon, rakuten, settings
                )

    finally:
        amazon.close()
        rakuten.close()

    logger.info("Pipeline complete: %d articles generated", articles_generated)


def _process_reviews(
    amazon: AmazonClient,
    rakuten: RakutenClient,
    settings,
    *,
    dry_run: bool,
) -> int:
    """Process unprocessed personal review memos."""
    logger.info("=== Phase A: Personal reviews ===")

    memos = read_review_memos(REVIEWS_DIR)
    unprocessed = get_unprocessed_memos(memos, settings.data_dir)

    if not unprocessed:
        logger.info("No new review memos to process")
        return 0

    logger.info("Found %d unprocessed review memos", len(unprocessed))

    if dry_run:
        for memo in unprocessed:
            logger.info("  [review] %s (%s)", memo.keyword, memo.filename)
        return 0

    if not settings.gemini_api_key:
        logger.error("GEMINI_API_KEY not set, cannot enrich reviews")
        return 0

    count = 0
    for memo in unprocessed:
        logger.info("Enriching review: %s", memo.keyword)

        # Search for the product on affiliate APIs
        products = _search_products(memo.keyword, amazon, rakuten)

        # Enrich with Gemini
        article = enrich_review(
            memo, products, gemini_api_key=settings.gemini_api_key
        )

        # Publish
        publish_article(article, output_dir=settings.site_content_dir)
        generate_ogp_image(
            article,
            output_dir=settings.data_dir.parent / "site" / "public" / "ogp",
        )

        mark_as_processed(memo.filename, settings.data_dir)
        count += 1
        logger.info("Published review: %s", article.meta.title)

    return count


def _process_comparisons(
    keywords: list[TrendKeyword],
    amazon: AmazonClient,
    rakuten: RakutenClient,
    settings,
) -> int:
    """Process comparison articles for discovered keywords."""
    count = 0

    for kw in keywords[: settings.daily_article_limit]:
        logger.info("Processing keyword: %s", kw.keyword)

        products = _search_products(kw.keyword, amazon, rakuten)
        if len(products) < 2:
            logger.info("  Insufficient products (%d), skipping", len(products))
            continue

        # Extract and normalize specs
        logger.info("  Extracting specs for %d products...", len(products))
        if settings.gemini_api_key:
            products = batch_extract_specs(
                products, gemini_api_key=settings.gemini_api_key
            )

        # Analyze and compare
        logger.info("  Building comparison...")
        comparison = build_comparison(kw.keyword, products)
        comparison.price_histories = record_prices(
            products, data_dir=settings.data_dir
        )

        # Generate article
        logger.info("  Generating article...")
        if not settings.gemini_api_key:
            logger.error("GEMINI_API_KEY not set, cannot generate articles")
            continue

        article = generate_comparison_article(
            comparison, gemini_api_key=settings.gemini_api_key
        )

        # Publish
        publish_article(article, output_dir=settings.site_content_dir)
        generate_ogp_image(
            article,
            output_dir=settings.data_dir.parent / "site" / "public" / "ogp",
        )

        count += 1
        logger.info("Published: %s", article.meta.title)

    return count


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
    parser.add_argument(
        "--reviews-only", action="store_true", help="Process personal reviews only"
    )
    args = parser.parse_args()

    try:
        run_pipeline(dry_run=args.dry_run, reviews_only=args.reviews_only)
    except KeyboardInterrupt:
        logger.info("Interrupted")
        sys.exit(130)
    except Exception:
        logger.exception("Pipeline failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
