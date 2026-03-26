"""Product/theme research using Gemini API.

Usage:
    python -m pipeline.research "ウイスキー 初心者 おすすめ"
    python -m pipeline.research "山崎12年 レビュー" --output data/research/
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------
class ResearchResult(BaseModel):
    """Structured research output for a given theme."""

    theme: str
    researched_at: datetime = Field(default_factory=datetime.now)
    raw_markdown: str = ""
    basic_info: dict = Field(default_factory=dict)
    user_reviews: dict = Field(default_factory=dict)
    comparison: dict = Field(default_factory=dict)
    target: dict = Field(default_factory=dict)
    search_intent: str = ""
    affiliate_angles: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
RESEARCH_SYSTEM_PROMPT = """\
あなたはプロのレビュアー兼アフィリエイトマーケターです。
与えられたテーマについて、事実ベースでリサーチし、以下の形式で出力してください。

# 絶対ルール
- 嘘や推測は禁止。曖昧な場合は「不明」と記載。
- 具体的な数値・商品名・価格を出す
- 箇条書きを多用し、読みやすくする
- 1文は60文字以内
"""

RESEARCH_USER_PROMPT = """\
# テーマ
{theme}

# 出力形式（Markdown）
以下の構成で出力してください。各セクションの見出しは必ずこの通りにしてください。

## 基本情報
- 商品名（またはテーマの概要）
- 価格帯
- 特徴（3つ、箇条書き）

## ユーザー評価
### 良い点
- （具体的に3〜5個）
### 悪い点
- （具体的に3〜5個）
### よくある後悔
- （具体的に2〜3個）

## 比較
- 類似商品・選択肢を2つ挙げる
- それぞれとの違いを明確に表形式で示す

| 比較軸 | {theme} | 類似A | 類似B |
|---|---|---|---|

## ターゲット
### 向いている人
- （3〜4個）
### 向いていない人
- （2〜3個）

## 検索意図
- このテーマで検索する人の目的を3つ

## アフィリエイト観点
### 購入を後押しするポイント
- （3〜4個）
### 購入を迷うポイント
- （2〜3個）
### おすすめの訴求切り口
- （X投稿やNote記事で使えるフック3つ）
"""


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------
def research_theme(
    theme: str,
    *,
    gemini_api_key: str,
    model_name: str = "gemini-2.5-flash",
) -> ResearchResult:
    """Run Gemini-powered research on a given theme."""
    logger.info("Researching: %s", theme)

    client = genai.Client(api_key=gemini_api_key)

    response = client.models.generate_content(
        model=model_name,
        contents=RESEARCH_USER_PROMPT.format(theme=theme),
        config=types.GenerateContentConfig(
            system_instruction=RESEARCH_SYSTEM_PROMPT,
            temperature=0.4,
            max_output_tokens=4096,
        ),
    )

    raw_md = response.text.strip()

    return ResearchResult(
        theme=theme,
        raw_markdown=raw_md,
    )


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
def save_research(result: ResearchResult, output_dir: Path) -> Path:
    """Save research result as Markdown + JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Slug from theme
    slug = result.theme.replace(" ", "-").replace("　", "-")
    ts = result.researched_at.strftime("%Y%m%d-%H%M%S")
    base_name = f"{ts}_{slug}"

    # Markdown (for human reading / Note posting)
    md_path = output_dir / f"{base_name}.md"
    md_content = f"""---
theme: "{result.theme}"
date: "{result.researched_at.isoformat()}"
---

# リサーチ: {result.theme}

{result.raw_markdown}
"""
    md_path.write_text(md_content, encoding="utf-8")
    logger.info("Saved: %s", md_path)

    # JSON (for programmatic use)
    json_path = output_dir / f"{base_name}.json"
    json_path.write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return md_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main() -> None:
    import argparse
    import sys

    from pipeline.config import get_settings

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Gemini API リサーチツール — テーマを渡すと構造化リサーチを実行",
        usage="python -m pipeline.research <テーマ> [options]",
    )
    parser.add_argument("theme", help="リサーチするテーマ（例: ウイスキー 初心者 おすすめ）")
    parser.add_argument(
        "--output", "-o",
        default="data/research",
        help="出力ディレクトリ（デフォルト: data/research）",
    )
    parser.add_argument(
        "--model", "-m",
        default="gemini-2.5-flash",
        help="Gemini モデル名（デフォルト: gemini-2.5-flash）",
    )
    parser.add_argument(
        "--print", "-p",
        action="store_true",
        dest="print_output",
        help="結果を標準出力にも表示",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.gemini_api_key:
        logger.error("GEMINI_API_KEY が設定されていません")
        logger.error("  export GEMINI_API_KEY=your-api-key")
        sys.exit(1)

    result = research_theme(
        args.theme,
        gemini_api_key=settings.gemini_api_key,
        model_name=args.model,
    )

    from pipeline.config import PROJECT_ROOT
    output_dir = PROJECT_ROOT / args.output
    md_path = save_research(result, output_dir)

    if args.print_output:
        print("\n" + "=" * 60)
        print(result.raw_markdown)
        print("=" * 60)

    print(f"\n✅ リサーチ完了: {result.theme}")
    print(f"📄 保存先: {md_path}")


if __name__ == "__main__":
    main()
