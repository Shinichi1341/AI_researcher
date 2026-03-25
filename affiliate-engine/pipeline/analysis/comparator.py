"""Multi-axis product comparison.

Builds a comparison matrix from normalized specs.
The comparison table is the primary content of the generated article —
not AI-generated prose.
"""

from __future__ import annotations

from pipeline.models import ComparisonAxis, ComparisonResult, Product
from pipeline.products.scorer import score_and_rank


def build_comparison(keyword: str, products: list[Product]) -> ComparisonResult:
    """Build a full comparison result for a set of products.

    Creates comparison axes from specs that are shared across
    at least 2 products, plus price and review axes.
    """
    if not products:
        return ComparisonResult(keyword=keyword, products=[])

    axes = _build_price_axis(products) + _build_review_axes(products) + _build_spec_axes(products)
    scores = score_and_rank(products)

    return ComparisonResult(
        keyword=keyword,
        products=products,
        axes=axes,
        scores=scores,
    )


def _build_price_axis(products: list[Product]) -> list[ComparisonAxis]:
    """Create price comparison axis with best price per platform."""
    values: dict[str, str] = {}
    for p in products:
        if p.prices:
            best = min(p.prices, key=lambda pp: pp.price)
            values[p.id] = f"¥{best.price:,}"
        else:
            values[p.id] = "—"

    best_id = ""
    min_price = float("inf")
    for p in products:
        for pp in p.prices:
            if pp.price > 0 and pp.price < min_price:
                min_price = pp.price
                best_id = p.id

    return [
        ComparisonAxis(
            axis_name="最安値",
            unit="円",
            values=values,
            best_product_id=best_id,
        )
    ]


def _build_review_axes(products: list[Product]) -> list[ComparisonAxis]:
    """Create review rating and count axes."""
    rating_values: dict[str, str] = {}
    count_values: dict[str, str] = {}

    for p in products:
        rating_values[p.id] = f"{p.review_rating:.1f}" if p.review_rating else "—"
        count_values[p.id] = f"{p.review_count:,}" if p.review_count else "—"

    best_rating = max(products, key=lambda p: p.review_rating, default=None)
    best_count = max(products, key=lambda p: p.review_count, default=None)

    return [
        ComparisonAxis(
            axis_name="レビュー評価",
            unit="/ 5.0",
            values=rating_values,
            best_product_id=best_rating.id if best_rating else "",
        ),
        ComparisonAxis(
            axis_name="レビュー件数",
            values=count_values,
            best_product_id=best_count.id if best_count else "",
        ),
    ]


def _build_spec_axes(products: list[Product]) -> list[ComparisonAxis]:
    """Create comparison axes from specs shared by ≥2 products."""
    # Count how many products have each spec name
    spec_freq: dict[str, int] = {}
    for p in products:
        for s in p.specs:
            spec_freq[s.name] = spec_freq.get(s.name, 0) + 1

    # Only include specs present in ≥2 products
    shared_specs = [name for name, count in spec_freq.items() if count >= 2]

    axes: list[ComparisonAxis] = []
    for spec_name in shared_specs:
        values: dict[str, str] = {}
        units: set[str] = set()

        for p in products:
            matching = [s for s in p.specs if s.name == spec_name]
            if matching:
                spec = matching[0]
                values[p.id] = f"{spec.value}{spec.unit}" if spec.unit else spec.value
                if spec.unit:
                    units.add(spec.unit)
            else:
                values[p.id] = "—"

        axes.append(
            ComparisonAxis(
                axis_name=spec_name,
                unit=units.pop() if len(units) == 1 else "",
                values=values,
            )
        )

    return axes
