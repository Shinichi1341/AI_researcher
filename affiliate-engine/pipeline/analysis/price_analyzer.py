"""Price history tracking and analysis.

Accumulates daily price snapshots to build unique historical data.
This data cannot be found on individual retailer sites and becomes
more valuable over time.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

from pipeline.models import Platform, PriceHistory, PriceHistoryEntry, Product

logger = logging.getLogger(__name__)


def record_prices(products: list[Product], *, data_dir: Path) -> list[PriceHistory]:
    """Record today's prices for all products and return updated histories."""
    price_dir = data_dir / "price_history"
    price_dir.mkdir(parents=True, exist_ok=True)
    today = date.today()

    histories: list[PriceHistory] = []

    for product in products:
        history = _load_history(product.id, product.title, price_dir)

        for pp in product.prices:
            if pp.price <= 0:
                continue

            # Avoid duplicate entries for the same date+platform
            already_recorded = any(
                e.date == today and e.platform == pp.platform for e in history.entries
            )
            if not already_recorded:
                history.entries.append(
                    PriceHistoryEntry(
                        date=today,
                        platform=pp.platform,
                        price=pp.price,
                    )
                )

        _save_history(history, price_dir)
        histories.append(history)

    return histories


def compute_price_stats(history: PriceHistory) -> dict:
    """Compute price statistics for a product's history."""
    if not history.entries:
        return {}

    by_platform: dict[str, list[int]] = {}
    for entry in history.entries:
        by_platform.setdefault(entry.platform.value, []).append(entry.price)

    stats: dict = {"product_id": history.product_id}

    for platform, prices in by_platform.items():
        stats[platform] = {
            "current": prices[-1],
            "min": min(prices),
            "max": max(prices),
            "avg": round(sum(prices) / len(prices)),
            "data_points": len(prices),
        }

        if len(prices) >= 2:
            recent = prices[-1]
            previous = prices[-2]
            change = recent - previous
            pct = (change / previous * 100) if previous > 0 else 0.0
            stats[platform]["change"] = change
            stats[platform]["change_pct"] = round(pct, 1)

    return stats


def find_best_platform(history: PriceHistory) -> Platform | None:
    """Determine which platform currently offers the best price."""
    today = date.today()

    latest: dict[Platform, int] = {}
    for entry in sorted(history.entries, key=lambda e: e.date, reverse=True):
        if entry.platform not in latest:
            latest[entry.platform] = entry.price

    if not latest:
        return None

    return min(latest, key=lambda p: latest[p])


def _load_history(product_id: str, title: str, price_dir: Path) -> PriceHistory:
    filepath = price_dir / f"{product_id}.json"
    if filepath.exists():
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            return PriceHistory.model_validate(data)
        except Exception:
            logger.warning("Failed to load price history for %s", product_id)

    return PriceHistory(product_id=product_id, product_title=title)


def _save_history(history: PriceHistory, price_dir: Path) -> None:
    filepath = price_dir / f"{history.product_id}.json"
    filepath.write_text(
        history.model_dump_json(indent=2),
        encoding="utf-8",
    )
