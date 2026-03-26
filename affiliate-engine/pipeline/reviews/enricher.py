"""Enrich a personal review memo into a full article using Gemini.

The user's authentic voice is preserved as the core of the article.
Gemini's role is strictly:
  1. Add objective data (awards, general reputation, price info)
  2. Structure the article for SEO
  3. Generate metadata
It must NOT rewrite or replace the user's own words.
"""

from __future__ import annotations

import json
import logging
import re

import google.generativeai as genai

from pipeline.models import Article, ArticleMeta, ArticleType, Product
from pipeline.reviews import ReviewMemo

logger = logging.getLogger(__name__)

_ENRICH_PROMPT = """\
あなたは酒類レビュー記事のエディターです。
以下の**著者本人のレビューメモ**を核にして、データで肉付けした記事を生成してください。

## 著者のレビューメモ（※ 原文のニュアンスを必ず保持すること）
キーワード: {keyword}
カテゴリ: {category}
著者評価: {rating}
---
{body}
---

## 商品の客観データ（API取得済み）
{product_data}

## 出力形式
以下のJSON形式で返してください。他のテキストは含めないでください。

{{
  "title": "60文字以内。「【正直レビュー】」等の冠をつけてよい",
  "description": "120文字以内のメタディスクリプション",
  "slug": "英数字とハイフンのURLスラッグ",
  "intro": "2〜3文の客観的な商品紹介（受賞歴・特徴など）",
  "objective_data": [
    {{"label": "データ項目名", "value": "値（例: 容量700ml, アルコール度数47%）"}}
  ],
  "pairing_suggestions": ["料理やおつまみの提案を2-3個"],
  "buying_guide": "購入時のアドバイス1〜2文（価格帯、どこが安いか等）"
}}

## ルール
- 著者のレビュー原文は変更してはいけない（記事では原文をそのまま掲載する）
- introには著者の感想を含めない。客観的事実のみ
- 景品表示法を遵守。「最高」「No.1」等の根拠なき表現禁止
- 推測は明記（「とされています」等）
- objective_dataは検証可能な事実のみ
"""


def enrich_review(
    memo: ReviewMemo,
    products: list[Product],
    *,
    gemini_api_key: str,
    model_name: str = "gemini-2.0-flash",
) -> Article:
    """Enrich a user's review memo into a full article."""
    product_data = _format_product_data(products)
    rating_str = f"{memo.rating:.1f}/5.0" if memo.rating else "未評価"

    prompt = _ENRICH_PROMPT.format(
        keyword=memo.keyword,
        category=memo.category,
        rating=rating_str,
        body=memo.body,
        product_data=product_data,
    )

    enriched = _call_gemini(prompt, gemini_api_key=gemini_api_key, model_name=model_name)

    # Build the article with user's review as the core
    content = _build_review_article(
        memo=memo,
        enriched=enriched,
        products=products,
    )

    slug = enriched.get("slug", memo.filename)
    slug = re.sub(r"[^a-z0-9-]", "-", slug.lower())
    slug = re.sub(r"-+", "-", slug).strip("-") or memo.filename

    from datetime import datetime

    now = datetime.now()

    meta = ArticleMeta(
        title=enriched.get("title", f"【正直レビュー】{memo.keyword}"),
        slug=slug,
        description=enriched.get("description", f"{memo.keyword}を実際に試した正直レビュー"),
        article_type=ArticleType.REVIEW,
        keyword=memo.keyword,
        category=memo.category,
        products=[p.id for p in products],
        created_at=now,
        updated_at=now,
    )

    return Article(meta=meta, content=content)


def _call_gemini(
    prompt: str,
    *,
    gemini_api_key: str,
    model_name: str,
) -> dict:
    """Call Gemini and return parsed JSON response."""
    try:
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.3,
            ),
        )
        return json.loads(response.text)
    except Exception:
        logger.exception("Gemini enrichment failed")
        return {}


def _build_review_article(
    memo: ReviewMemo,
    enriched: dict,
    products: list[Product],
) -> str:
    """Assemble the full article from user review + enriched data."""
    parts: list[str] = []

    # Intro from Gemini (objective facts only)
    intro = enriched.get("intro", "")
    if intro:
        parts.append(intro)
        parts.append("")

    # Objective data table
    obj_data = enriched.get("objective_data", [])
    if obj_data:
        parts.append("## 基本データ")
        parts.append("")
        parts.append("| 項目 | 詳細 |")
        parts.append("| --- | --- |")
        for item in obj_data:
            parts.append(f"| {item.get('label', '')} | {item.get('value', '')} |")
        parts.append("")

    # User's authentic review (THE CORE - untouched)
    parts.append("## 飲んでみた正直な感想")
    parts.append("")
    if memo.rating:
        parts.append(f"**筆者評価: {'★' * int(memo.rating)}{'☆' * (5 - int(memo.rating))} ({memo.rating:.1f}/5.0)**")
        parts.append("")
    parts.append(memo.body)
    parts.append("")

    # Pairing suggestions from Gemini
    pairings = enriched.get("pairing_suggestions", [])
    if pairings:
        parts.append("## おすすめの合わせ方")
        parts.append("")
        for p in pairings:
            parts.append(f"- {p}")
        parts.append("")

    # Price comparison from API data
    if products:
        parts.append("## 価格比較")
        parts.append("")
        parts.append("| 購入先 | 価格 | リンク |")
        parts.append("| --- | --- | --- |")
        for product in products:
            for pp in product.prices:
                label = "Amazon" if pp.platform.value == "amazon" else "楽天市場"
                link = f"[{label}で見る]({pp.affiliate_url})" if pp.affiliate_url else "—"
                parts.append(f"| {label} | ¥{pp.price:,} | {link} |")
        parts.append("")

    # Buying guide
    guide = enriched.get("buying_guide", "")
    if guide:
        parts.append(f"> {guide}")
        parts.append("")

    # Disclaimer
    parts.append("---")
    parts.append("")
    parts.append(
        "*※ 本記事は筆者が実際に購入・試飲した体験に基づくレビューです。"
        "価格は記事更新時点のものです。"
        "当サイトはアフィリエイトプログラムに参加しており、"
        "リンク経由の購入で紹介料を受け取る場合があります。*"
    )

    return "\n".join(parts)


def _format_product_data(products: list[Product]) -> str:
    """Format product API data for the Gemini prompt."""
    if not products:
        return "（商品データなし — 一般的な情報で補完してください）"

    lines: list[str] = []
    for p in products:
        lines.append(f"- 商品名: {p.title}")
        lines.append(f"  ブランド: {p.brand}")
        if p.prices:
            prices_str = ", ".join(
                f"{pp.platform.value}: ¥{pp.price:,}" for pp in p.prices
            )
            lines.append(f"  価格: {prices_str}")
        if p.review_rating:
            lines.append(f"  レビュー: {p.review_rating:.1f}/5.0 ({p.review_count}件)")
        if p.specs:
            specs_str = ", ".join(f"{s.name}: {s.value}{s.unit}" for s in p.specs)
            lines.append(f"  スペック: {specs_str}")

    return "\n".join(lines)
