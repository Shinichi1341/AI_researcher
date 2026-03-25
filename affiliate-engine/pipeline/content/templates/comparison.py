"""Comparison article template.

Generates structured comparison articles where the primary content
is the comparison table and score breakdown — NOT AI prose filler.
Gemini is used to write a concise factual introduction only.
"""

from __future__ import annotations

from pipeline.analysis.price_analyzer import compute_price_stats
from pipeline.models import ComparisonResult, Product


def build_comparison_table(result: ComparisonResult) -> str:
    """Build a Markdown comparison table from comparison axes."""
    if not result.products or not result.axes:
        return ""

    # Header row: | 比較項目 | Product1 | Product2 | ...
    short_names = {p.id: _short_name(p) for p in result.products}
    headers = ["比較項目"] + [short_names[p.id] for p in result.products]
    separator = ["-" * max(3, len(h)) for h in headers]

    rows: list[list[str]] = []
    for axis in result.axes:
        row = [f"**{axis.axis_name}**"]
        for p in result.products:
            val = axis.values.get(p.id, "—")
            # Highlight best
            if axis.best_product_id == p.id and val != "—":
                val = f"**{val}** ✓"
            row.append(val)
        rows.append(row)

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def build_score_table(result: ComparisonResult) -> str:
    """Build a scoring breakdown table."""
    if not result.scores:
        return ""

    headers = ["順位", "商品名", "総合スコア", "コスパ", "評価", "人気度", "スペック", "購入先"]
    separator = ["-" * max(3, len(h)) for h in headers]

    short_names = {p.id: _short_name(p) for p in result.products}
    product_map = {p.id: p for p in result.products}

    rows: list[list[str]] = []
    for score in result.scores:
        p = product_map.get(score.product_id)
        if not p:
            continue

        dims = {b.dimension: b.normalized for b in score.breakdown}
        bar = lambda v: _score_bar(v)  # noqa: E731

        rows.append([
            f"**{score.rank}位**",
            short_names.get(score.product_id, "—"),
            f"**{score.total_score:.2f}**",
            bar(dims.get("price_competitiveness", 0)),
            bar(dims.get("review_rating", 0)),
            bar(dims.get("review_volume", 0)),
            bar(dims.get("spec_richness", 0)),
            _platform_label(p),
        ])

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def build_price_section(result: ComparisonResult) -> str:
    """Build price history and cross-platform comparison section."""
    if not result.price_histories:
        return ""

    sections: list[str] = []
    product_map = {p.id: p for p in result.products}

    for history in result.price_histories:
        stats = compute_price_stats(history)
        if not stats:
            continue

        p = product_map.get(history.product_id)
        name = _short_name(p) if p else history.product_title

        lines = [f"### {name}"]

        for platform_key in ("amazon", "rakuten"):
            plat = stats.get(platform_key)
            if not plat:
                continue

            label = "Amazon" if platform_key == "amazon" else "楽天市場"
            lines.append(f"\n**{label}**")
            lines.append(f"- 現在価格: ¥{plat['current']:,}")
            lines.append(f"- 最安値: ¥{plat['min']:,}")
            lines.append(f"- 最高値: ¥{plat['max']:,}")
            lines.append(f"- 平均価格: ¥{plat['avg']:,}")

            if "change_pct" in plat:
                direction = "↑" if plat["change"] > 0 else "↓"
                lines.append(f"- 前回比: {direction} {abs(plat['change_pct'])}%")

        sections.append("\n".join(lines))

    return "\n\n".join(sections)


INTRO_PROMPT = """\
以下の商品比較データに基づいて、検索キーワード「{keyword}」で訪問した読者向けに
簡潔な導入文（3〜4文）を日本語で書いてください。

## ルール
- 事実のみ記述し、主観的な感想や推薦は含めない
- 「この記事では」等のメタ表現を使わない
- 比較対象の商品数と主要な比較ポイントに触れる
- 景品表示法を遵守し、誇大表現を避ける

## データ
商品数: {product_count}
比較軸: {axes}
価格帯: {price_range}
"""


def build_intro_prompt(result: ComparisonResult) -> str:
    """Build a Gemini prompt for the article introduction."""
    prices = []
    for p in result.products:
        for pp in p.prices:
            if pp.price > 0:
                prices.append(pp.price)

    price_range = (
        f"¥{min(prices):,}〜¥{max(prices):,}" if prices else "情報なし"
    )

    axes = ", ".join(a.axis_name for a in result.axes[:8])

    return INTRO_PROMPT.format(
        keyword=result.keyword,
        product_count=len(result.products),
        axes=axes,
        price_range=price_range,
    )


def _short_name(product: Product) -> str:
    """Shorten product title for table readability."""
    title = product.title
    if len(title) > 30:
        title = title[:28] + "…"
    return title


def _score_bar(value: float) -> str:
    """Visual score bar using Unicode blocks."""
    filled = round(value * 5)
    return "█" * filled + "░" * (5 - filled)


def _platform_label(product: Product) -> str:
    labels = []
    for pp in product.prices:
        if pp.platform.value == "amazon":
            labels.append("Amazon")
        elif pp.platform.value == "rakuten":
            labels.append("楽天")
    return " / ".join(labels) if labels else "—"
