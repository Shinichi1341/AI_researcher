"""Product scoring with transparent, reproducible algorithm.

Each product is scored across multiple dimensions with explicit weights.
This transparency is itself a content differentiator — users can see
exactly why a product is recommended.
"""

from __future__ import annotations

from pipeline.models import Platform, Product, ProductScore, ScoreBreakdown

# Scoring weights (must sum to 1.0)
WEIGHTS = {
    "price_competitiveness": 0.30,
    "review_rating": 0.25,
    "review_volume": 0.20,
    "spec_richness": 0.15,
    "cross_platform": 0.10,
}


def score_product(product: Product, all_products: list[Product]) -> ProductScore:
    """Score a single product relative to the comparison set."""
    breakdown: list[ScoreBreakdown] = []

    # 1) Price competitiveness (lower is better)
    prices = [_best_price(p) for p in all_products if _best_price(p) > 0]
    my_price = _best_price(product)
    if prices and my_price > 0:
        min_price = min(prices)
        max_price = max(prices)
        price_range = max_price - min_price
        normalized = 1.0 - ((my_price - min_price) / price_range) if price_range > 0 else 0.5
    else:
        normalized = 0.5
    breakdown.append(
        ScoreBreakdown(
            dimension="price_competitiveness",
            raw_value=float(my_price),
            normalized=_clamp(normalized),
            weight=WEIGHTS["price_competitiveness"],
            weighted_score=_clamp(normalized) * WEIGHTS["price_competitiveness"],
        )
    )

    # 2) Review rating (0-5 scale)
    rating_norm = product.review_rating / 5.0 if product.review_rating else 0.0
    breakdown.append(
        ScoreBreakdown(
            dimension="review_rating",
            raw_value=product.review_rating,
            normalized=_clamp(rating_norm),
            weight=WEIGHTS["review_rating"],
            weighted_score=_clamp(rating_norm) * WEIGHTS["review_rating"],
        )
    )

    # 3) Review volume (log-scaled relative to max in set)
    import math

    volumes = [p.review_count for p in all_products if p.review_count > 0]
    max_vol = max(volumes) if volumes else 1
    vol_norm = math.log1p(product.review_count) / math.log1p(max_vol) if max_vol > 0 else 0.0
    breakdown.append(
        ScoreBreakdown(
            dimension="review_volume",
            raw_value=float(product.review_count),
            normalized=_clamp(vol_norm),
            weight=WEIGHTS["review_volume"],
            weighted_score=_clamp(vol_norm) * WEIGHTS["review_volume"],
        )
    )

    # 4) Spec richness (more structured specs = more comparison value)
    spec_counts = [len(p.specs) for p in all_products]
    max_specs = max(spec_counts) if spec_counts else 1
    spec_norm = len(product.specs) / max_specs if max_specs > 0 else 0.0
    breakdown.append(
        ScoreBreakdown(
            dimension="spec_richness",
            raw_value=float(len(product.specs)),
            normalized=_clamp(spec_norm),
            weight=WEIGHTS["spec_richness"],
            weighted_score=_clamp(spec_norm) * WEIGHTS["spec_richness"],
        )
    )

    # 5) Cross-platform availability bonus
    platforms = {pp.platform for pp in product.prices}
    cp_norm = 1.0 if len(platforms) > 1 else 0.5
    breakdown.append(
        ScoreBreakdown(
            dimension="cross_platform",
            raw_value=float(len(platforms)),
            normalized=cp_norm,
            weight=WEIGHTS["cross_platform"],
            weighted_score=cp_norm * WEIGHTS["cross_platform"],
        )
    )

    total = sum(b.weighted_score for b in breakdown)

    return ProductScore(
        product_id=product.id,
        total_score=round(total, 4),
        breakdown=breakdown,
    )


def score_and_rank(products: list[Product]) -> list[ProductScore]:
    """Score all products and assign ranks."""
    scores = [score_product(p, products) for p in products]
    scores.sort(key=lambda s: s.total_score, reverse=True)
    for i, s in enumerate(scores, 1):
        s.rank = i
    return scores


def _best_price(product: Product) -> int:
    """Return the lowest available price across platforms."""
    available = [p.price for p in product.prices if p.price > 0]
    return min(available) if available else 0


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))
