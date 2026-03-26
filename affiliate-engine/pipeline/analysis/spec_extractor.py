"""Extract and normalize product specifications using Gemini.

Uses Gemini's structured output to transform free-text product
descriptions into normalized, comparable spec sheets.
This is a key differentiator: individual product pages have
inconsistent spec formats, but we unify them.
"""

from __future__ import annotations

import json
import logging

import google.generativeai as genai

from pipeline.models import Product, ProductSpec

logger = logging.getLogger(__name__)

_EXTRACTION_PROMPT = """\
あなたは商品スペック抽出の専門家です。
以下の商品情報から、比較に役立つスペック（仕様）を構造化JSONとして抽出してください。

## 商品情報
タイトル: {title}
ブランド: {brand}
カテゴリ: {category}
説明文: {description}
既存スペック: {existing_specs}

## 出力形式
以下のJSON配列を返してください。他のテキストは含めないでください。
[
  {{"name": "スペック名", "value": "値", "unit": "単位（あれば）"}}
]

## ルール
- 比較に有用なスペックのみ抽出（サイズ、重量、消費電力、容量、材質など）
- 単位は統一（cm, kg, W, mAh など SI 系を優先）
- 推測ではなく、テキストに明記された情報のみ抽出
- 最大15項目まで
"""


def extract_specs(
    product: Product,
    *,
    gemini_api_key: str,
    model_name: str = "gemini-2.5-flash",
) -> list[ProductSpec]:
    """Extract structured specs from a product using Gemini.

    Falls back to existing specs if Gemini call fails.
    """
    if not product.description and not product.specs:
        return product.specs

    existing = ", ".join(f"{s.name}: {s.value}{s.unit}" for s in product.specs)

    prompt = _EXTRACTION_PROMPT.format(
        title=product.title,
        brand=product.brand,
        category=product.category,
        description=product.description[:2000],
        existing_specs=existing or "なし",
    )

    try:
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

        specs_data = json.loads(response.text)
        return [
            ProductSpec(
                name=item["name"],
                value=str(item["value"]),
                unit=item.get("unit", ""),
            )
            for item in specs_data
            if "name" in item and "value" in item
        ]

    except Exception:
        logger.warning("Spec extraction failed for %s, using existing specs", product.id)
        return product.specs


def batch_extract_specs(
    products: list[Product],
    *,
    gemini_api_key: str,
) -> list[Product]:
    """Extract and attach normalized specs for all products."""
    updated: list[Product] = []
    for product in products:
        new_specs = extract_specs(product, gemini_api_key=gemini_api_key)
        updated.append(product.model_copy(update={"specs": new_specs}))
    return updated
