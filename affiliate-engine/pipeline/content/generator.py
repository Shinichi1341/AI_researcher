"""Article generator using Gemini + structured data.

The philosophy: AI generates minimal prose. The article's value
comes from structured data (comparison tables, score breakdowns,
price analysis) that is computed deterministically.
Gemini's role is limited to:
  1. Writing a concise factual introduction (3-4 sentences)
  2. Generating SEO metadata
"""

from __future__ import annotations

import logging
from datetime import datetime

import google.generativeai as genai

from pipeline.content.seo import generate_seo_meta
from pipeline.content.templates.comparison import (
    build_comparison_table,
    build_intro_prompt,
    build_price_section,
    build_score_table,
)
from pipeline.models import Article, ArticleMeta, ArticleType, ComparisonResult

logger = logging.getLogger(__name__)


def generate_comparison_article(
    result: ComparisonResult,
    *,
    gemini_api_key: str,
    model_name: str = "gemini-2.0-flash",
) -> Article:
    """Generate a complete comparison article from analysis results."""
    # 1. Generate SEO metadata
    seo = generate_seo_meta(
        keyword=result.keyword,
        category=result.products[0].category if result.products else "",
        product_count=len(result.products),
        article_type="comparison",
        gemini_api_key=gemini_api_key,
        model_name=model_name,
    )

    # 2. Generate concise intro using Gemini
    intro = _generate_intro(result, gemini_api_key=gemini_api_key, model_name=model_name)

    # 3. Build structured data sections (NO AI prose here)
    comparison_table = build_comparison_table(result)
    score_table = build_score_table(result)
    price_section = build_price_section(result)

    # 4. Build product detail sections with affiliate links
    product_sections = _build_product_sections(result)

    # 5. Assemble the article
    now = datetime.now()
    content = _assemble_article(
        intro=intro,
        comparison_table=comparison_table,
        score_table=score_table,
        price_section=price_section,
        product_sections=product_sections,
        keyword=result.keyword,
        updated=now.strftime("%Y年%m月%d日"),
    )

    meta = ArticleMeta(
        title=seo.get("title", f"{result.keyword} 比較"),
        slug=seo.get("slug", "comparison"),
        description=seo.get("description", ""),
        article_type=ArticleType.COMPARISON,
        keyword=result.keyword,
        category=result.products[0].category if result.products else "",
        products=[p.id for p in result.products],
        created_at=now,
        updated_at=now,
    )

    return Article(
        meta=meta,
        content=content,
        comparison_table_md=comparison_table,
        score_table_md=score_table,
    )


def _generate_intro(
    result: ComparisonResult,
    *,
    gemini_api_key: str,
    model_name: str,
) -> str:
    """Generate a short factual introduction using Gemini."""
    prompt = build_intro_prompt(result)

    try:
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(temperature=0.3, max_output_tokens=300),
        )
        return response.text.strip()
    except Exception:
        logger.warning("Intro generation failed, using fallback")
        n = len(result.products)
        return (
            f"「{result.keyword}」で人気の{n}商品を、"
            f"価格・スペック・レビュー評価の{len(result.axes)}項目で比較しました。"
        )


def _build_product_sections(result: ComparisonResult) -> str:
    """Build individual product detail sections with affiliate links."""
    sections: list[str] = []
    score_map = {s.product_id: s for s in result.scores}

    for product in result.products:
        score = score_map.get(product.id)
        rank = score.rank if score else 0
        total = score.total_score if score else 0.0

        lines = [f"### {rank}位: {product.title}"]
        lines.append("")

        if product.brand:
            lines.append(f"**ブランド**: {product.brand}")

        # Price per platform
        for pp in product.prices:
            label = "Amazon" if pp.platform.value == "amazon" else "楽天市場"
            lines.append(f"**{label}価格**: ¥{pp.price:,}")

        if product.review_rating:
            lines.append(
                f"**レビュー**: {product.review_rating:.1f}/5.0 ({product.review_count:,}件)"
            )

        lines.append(f"**総合スコア**: {total:.2f}")
        lines.append("")

        # Specs
        if product.specs:
            lines.append("<details>")
            lines.append("<summary>スペック詳細</summary>")
            lines.append("")
            for spec in product.specs:
                val = f"{spec.value} {spec.unit}".strip()
                lines.append(f"- **{spec.name}**: {val}")
            lines.append("")
            lines.append("</details>")
            lines.append("")

        # Affiliate links
        for pp in product.prices:
            if pp.affiliate_url:
                label = "Amazonで見る" if pp.platform.value == "amazon" else "楽天市場で見る"
                lines.append(f"[{label}]({pp.affiliate_url})")

        sections.append("\n".join(lines))

    return "\n\n---\n\n".join(sections)


def _assemble_article(
    *,
    intro: str,
    comparison_table: str,
    score_table: str,
    price_section: str,
    product_sections: str,
    keyword: str,
    updated: str,
) -> str:
    """Assemble all sections into a complete Markdown article."""
    parts = [
        intro,
        "",
        "## 比較表",
        "",
        comparison_table,
        "",
        "## 総合ランキング",
        "",
        score_table,
        "",
    ]

    if price_section:
        parts.extend([
            "## 価格推移",
            "",
            price_section,
            "",
        ])

    parts.extend([
        "## 各商品の詳細",
        "",
        product_sections,
        "",
        "---",
        "",
        f"*最終更新: {updated}*",
        "",
        (
            "※ 価格は記事更新時点のものです。最新の価格は各販売サイトでご確認ください。"
            "当サイトはアフィリエイトプログラムに参加しており、"
            "リンク経由の購入で紹介料を受け取る場合があります。"
        ),
    ])

    return "\n".join(parts)
