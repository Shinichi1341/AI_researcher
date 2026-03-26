"""SEO metadata generation using Gemini."""

from __future__ import annotations

import json
import logging
import re

import google.generativeai as genai

logger = logging.getLogger(__name__)

_SEO_PROMPT = """\
以下の記事情報から、SEOに最適化されたメタデータをJSON形式で生成してください。

## 記事情報
キーワード: {keyword}
カテゴリ: {category}
商品数: {product_count}
記事タイプ: {article_type}

## 出力形式（JSON のみ返してください）
{{
  "title": "60文字以内のSEOタイトル。キーワードを含む",
  "description": "120文字以内のメタディスクリプション",
  "slug": "英数字とハイフンのみのURLスラッグ"
}}

## ルール
- タイトルにはキーワードを自然に含める
- タイトルに「【{year}年最新】」等の時期情報を含める
- description は検索結果のスニペットとして魅力的に
- 誇大表現は避ける
"""


def generate_seo_meta(
    keyword: str,
    category: str,
    product_count: int,
    article_type: str,
    *,
    gemini_api_key: str,
    model_name: str = "gemini-2.5-flash",
) -> dict[str, str]:
    """Generate SEO-optimized metadata using Gemini."""
    from datetime import datetime

    prompt = _SEO_PROMPT.format(
        keyword=keyword,
        category=category,
        product_count=product_count,
        article_type=article_type,
        year=datetime.now().year,
    )

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
        meta = json.loads(response.text)

        # Sanitize slug
        slug = meta.get("slug", keyword)
        slug = re.sub(r"[^a-z0-9-]", "-", slug.lower())
        slug = re.sub(r"-+", "-", slug).strip("-")
        meta["slug"] = slug

        return meta

    except Exception:
        logger.warning("SEO meta generation failed, using fallback")
        slug = re.sub(r"[^a-z0-9-]", "-", keyword.lower())
        slug = re.sub(r"-+", "-", slug).strip("-") or "article"
        return {
            "title": f"{keyword} おすすめ{product_count}選 比較",
            "description": f"{keyword}の人気{product_count}商品を徹底比較。",
            "slug": slug,
        }
