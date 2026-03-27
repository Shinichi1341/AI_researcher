"""Product/theme research using Gemini API.

Usage:
    # Auto mode (fully automated research)
    python -m pipeline.research "ウイスキー 初心者 おすすめ" --mode auto -a
    # Review mode (user's personal review + supplementary research)
    python -m pipeline.research "山崎12年" --mode review --review "実際に飲んでみた感想..."  -a
    # JSON output
    python -m pipeline.research "テーマ" --mode auto -a --json
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from enum import Enum
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Mode(str, Enum):
    AUTO = "auto"
    REVIEW = "review"


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------
class ResearchResult(BaseModel):
    """Structured research output for a given theme."""

    theme: str
    mode: str = "auto"
    researched_at: datetime = Field(default_factory=datetime.now)
    raw_markdown: str = ""
    user_review: str = ""
    basic_info: dict = Field(default_factory=dict)
    user_reviews: dict = Field(default_factory=dict)
    comparison: dict = Field(default_factory=dict)
    target: dict = Field(default_factory=dict)
    search_intent: str = ""
    affiliate_angles: dict = Field(default_factory=dict)


class UnifiedOutput(BaseModel):
    """Unified JSON output containing all generated artifacts."""

    theme: str
    mode: str
    generated_at: datetime = Field(default_factory=datetime.now)
    research: dict = Field(default_factory=dict)
    x_posts: str = ""
    note_article: str = ""


# ---------------------------------------------------------------------------
# Prompts — Auto mode
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
# Prompts — Review mode (user's personal review is primary)
# ---------------------------------------------------------------------------
REVIEW_RESEARCH_SYSTEM_PROMPT = """\
あなたはプロのレビュアー兼アフィリエイトマーケターのアシスタントです。
ユーザーが自分の体験レビューを提供します。
そのレビューを最大限に活かしつつ、補足リサーチで記事素材を充実させてください。

# 絶対ルール
- ユーザーのレビュー内容が最優先。改変しない。
- 補足情報は「ユーザーの感想を裏付ける」方向で出す
- 嘘や推測は禁止。曖昧な場合は「不明」と記載
- 具体的な数値・商品名・価格を出す
- 1文は60文字以内
"""

REVIEW_RESEARCH_USER_PROMPT = """\
# テーマ
{theme}

# ユーザーの体験レビュー（これが最重要。必ず活かすこと）
{user_review}

# 出力形式（Markdown）
ユーザーのレビューを軸に、以下を補足リサーチして出力してください。

## ユーザーレビュー要約
- ユーザーの体験から得られたポイントを3〜5個抽出

## 補足リサーチ
### 基本情報
- 商品名・価格帯・特徴（3つ）
### 世間の評価との比較
- ユーザーの感想と世間の評価の一致/相違点
### 類似商品との比較
| 比較軸 | {theme} | 類似A | 類似B |
|---|---|---|---|

## ターゲット
### 向いている人
- （ユーザーの体験を踏まえて3〜4個）
### 向いていない人
- （2〜3個）

## アフィリエイト観点
### ユーザー体験から使える訴求ポイント
- （3〜4個、レビューの具体的エピソードを引用）
### 購入を迷うポイント
- （2〜3個）
### おすすめの訴求切り口
- （X投稿やNote記事で使えるフック3つ）
"""

REVIEW_X_POST_SYSTEM_PROMPT = """\
あなたはバズるSNSマーケターです。
ユーザーの実体験レビューを元に、X（旧Twitter）投稿を3パターン作成してください。

# 絶対ルール
- 各投稿は140文字以内（厳守）
- ユーザーの体験エピソードを必ず1つ以上含める
- リアルな体験談ベースで書く
- 誇張NG、一人称で書く
- 「知らないと損」「正直」「結論」などのフックを入れる
- 最後に「詳細はNoteで→」を自然に入れる
- 絵文字は1〜2個まで
"""

REVIEW_X_POST_USER_PROMPT = """\
# テーマ
{theme}

# ユーザーの体験レビュー（これが最重要素材）
{user_review}

# 補足リサーチ
{research_md}

# 出力形式（この通りに出力）

## 投稿①（体験型）
（ユーザーの実体験をベースに140文字以内）

## 投稿②（比較・発見型）
（体験から得た気づき・比較を140文字以内）

## 投稿③（おすすめ型）
（体験を踏まえた本音のおすすめを140文字以内）
"""

REVIEW_NOTE_SYSTEM_PROMPT = """\
あなたはプロのレビューライター兼アフィリエイターのアシスタントです。
ユーザーの実体験レビューを主軸に、収益化を意識したNote記事を作成してください。

# 絶対ルール
- 2000〜3000文字（厳守）
- ユーザーのレビュー内容を最優先で使う
- ユーザーの言葉・表現をできるだけそのまま活かす
- 補足リサーチは「裏付け」「深掘り」として自然に織り込む
- 結論ファースト
- 1文は60文字以内
- 2〜3文ごとに改行

# トーン
- 一人称の体験記風（ユーザー本人が書いたように）
- 正直レビュー
- 「正直〜」「ぶっちゃけ〜」「結論から言うと〜」のようなフック
"""

REVIEW_NOTE_USER_PROMPT = """\
# テーマ
{theme}

# ユーザーの体験レビュー（これが記事の核。必ずこの内容を軸にすること）
{user_review}

# 補足リサーチ結果（裏付け情報として自然に織り込む）
{research_md}

# 記事構成（この見出し構成で書くこと）

## タイトル
（体験ベースのクリックしたくなるタイトル。30〜40文字。【】を使う）

## 結論（最初に）
（ユーザーの体験からの結論を3行以内。箇条書き3つでポイント）

## 実際のレビュー
（ユーザーのレビューをベースに構成。第一印象・香り・味・飲み方など。
 ユーザーの言葉をできるだけ活かしつつ、読みやすく整形。
 補足リサーチで裏付けを自然に追加）

## メリット・デメリット
### メリット
- （ユーザー体験ベースで3〜4個）
### デメリット
- （ユーザーが感じた点ベースで2〜3個、正直に）

## 他製品との比較
（表形式で2製品と比較。ユーザーの体験があれば優先的に使用）

## こんな人におすすめ
- （ユーザーの体験を踏まえて3〜4個、絵文字付き）

## 注意点（ここ重要）
（ユーザーが感じた注意点 + 補足リサーチから2〜3個）

## まとめ
（3行で結論。最後に自然な購入導線を1文だけ）

---
※ ユーザーの体験レビューの内容を最優先で使い、補足リサーチは裏付けとして自然に織り込んでください。
※ 全体で2000〜3000文字に収めてください。
"""


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------
def research_theme(
    theme: str,
    *,
    gemini_api_key: str,
    model_name: str = "gemini-2.5-flash",
    mode: Mode = Mode.AUTO,
    user_review: str = "",
) -> ResearchResult:
    """Run Gemini-powered research on a given theme."""
    logger.info("Researching [%s mode]: %s", mode.value, theme)

    client = genai.Client(api_key=gemini_api_key)

    if mode == Mode.REVIEW:
        if not user_review:
            raise ValueError("review モードでは --review でレビューテキストが必要です")
        system_prompt = REVIEW_RESEARCH_SYSTEM_PROMPT
        user_prompt = REVIEW_RESEARCH_USER_PROMPT.format(
            theme=theme, user_review=user_review,
        )
    else:
        system_prompt = RESEARCH_SYSTEM_PROMPT
        user_prompt = RESEARCH_USER_PROMPT.format(theme=theme)

    response = client.models.generate_content(
        model=model_name,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.4,
            max_output_tokens=4096,
        ),
    )

    raw_md = response.text.strip()

    return ResearchResult(
        theme=theme,
        mode=mode.value,
        raw_markdown=raw_md,
        user_review=user_review,
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
# X (Twitter) post generation
# ---------------------------------------------------------------------------
X_POST_SYSTEM_PROMPT = """\
あなたはバズるSNSマーケターです。
与えられたリサーチ結果を元に、X（旧Twitter）投稿を3パターン作成してください。

# 絶対ルール
- 各投稿は140文字以内（厳守）
- 日本語で書く
- 誇張NG、リアル重視
- 思わずクリックしたくなる構成にする
- 「知らないと損」「正直」「結論」などのフックを入れる
- 最後に「詳細はNoteで→」を自然に入れる
- 絵文字は1〜2個まで
"""

X_POST_USER_PROMPT = """\
# テーマ
{theme}

# リサーチ結果
{research_md}

# 出力形式（この通りに出力）

## 投稿①（比較型）
（ここに140文字以内の投稿文）

## 投稿②（失敗談型）
（ここに140文字以内の投稿文）

## 投稿③（数値・事実型）
（ここに140文字以内の投稿文）
"""


def generate_x_posts(
    result: ResearchResult,
    *,
    gemini_api_key: str,
    model_name: str = "gemini-2.5-flash",
) -> str:
    """Generate 3 X post drafts from research result."""
    logger.info("Generating X posts [%s mode] for: %s", result.mode, result.theme)

    client = genai.Client(api_key=gemini_api_key)

    if result.mode == Mode.REVIEW.value and result.user_review:
        system_prompt = REVIEW_X_POST_SYSTEM_PROMPT
        user_prompt = REVIEW_X_POST_USER_PROMPT.format(
            theme=result.theme,
            user_review=result.user_review,
            research_md=result.raw_markdown,
        )
    else:
        system_prompt = X_POST_SYSTEM_PROMPT
        user_prompt = X_POST_USER_PROMPT.format(
            theme=result.theme,
            research_md=result.raw_markdown,
        )

    response = client.models.generate_content(
        model=model_name,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.7,
            max_output_tokens=2048,
        ),
    )

    return response.text.strip()


def save_x_posts(theme: str, posts_md: str, output_dir: Path) -> Path:
    """Save X posts to a text file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = theme.replace(" ", "-").replace("　", "-")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = output_dir / f"{ts}_{slug}_x-posts.md"
    path.write_text(posts_md, encoding="utf-8")
    logger.info("Saved X posts: %s", path)
    return path


# ---------------------------------------------------------------------------
# Note article generation
# ---------------------------------------------------------------------------
NOTE_SYSTEM_PROMPT = """\
あなたはプロのレビューライター兼アフィリエイターです。
与えられたリサーチ結果を元に、収益化を意識したNote記事を作成してください。

# 絶対ルール
- 2000〜3000文字（厳守）
- 読みやすい日本語
- 結論ファースト
- 信頼性重視（体験ベース風に書く）
- 1文は60文字以内
- 2〜3文ごとに改行
- 箇条書きを積極的に使う

# アフィリエイト導線ルール
- 自然に購入したくなる流れを作る
- 押し売り感はNG
- 「気になった方はチェックしてみてください」程度の誘導

# トーン
- 個人ブログ風
- 正直レビュー
- 「正直〜」「ぶっちゃけ〜」「結論から言うと〜」のようなフック
"""

NOTE_USER_PROMPT = """\
# テーマ
{theme}

# リサーチ結果
{research_md}

# 記事構成（この見出し構成で書くこと）

## タイトル
（クリックしたくなるタイトル。30〜40文字。【】を使う）

## 結論（最初に）
（3行以内で結論を述べる。その後、箇条書き3つでポイント）

## 実際のレビュー
（体験ベース風に書く。第一印象・香り・味・飲み方など具体的に。
 主観と客観を分けて記述）

## メリット・デメリット
### メリット
- （3〜4個）
### デメリット
- （2〜3個、正直に書く）

## 他製品との比較
（表形式で2製品と比較。違いを明確に）

## こんな人におすすめ
- （3〜4個、絵文字付き）

## 注意点（ここ重要）
（購入前に知っておくべきこと2〜3個。正直に書くことで信頼感UP）

## まとめ
（3行で結論。最後に自然な購入導線を1文だけ）

---
※ Noteの文字数制限のため、全体で2000〜3000文字に収めてください。
"""


def generate_note_article(
    result: ResearchResult,
    *,
    gemini_api_key: str,
    model_name: str = "gemini-2.5-flash",
) -> str:
    """Generate a Note article draft from research result."""
    logger.info("Generating Note article [%s mode] for: %s", result.mode, result.theme)

    client = genai.Client(api_key=gemini_api_key)

    if result.mode == Mode.REVIEW.value and result.user_review:
        system_prompt = REVIEW_NOTE_SYSTEM_PROMPT
        user_prompt = REVIEW_NOTE_USER_PROMPT.format(
            theme=result.theme,
            user_review=result.user_review,
            research_md=result.raw_markdown,
        )
    else:
        system_prompt = NOTE_SYSTEM_PROMPT
        user_prompt = NOTE_USER_PROMPT.format(
            theme=result.theme,
            research_md=result.raw_markdown,
        )

    response = client.models.generate_content(
        model=model_name,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.6,
            max_output_tokens=8192,
        ),
    )

    return response.text.strip()


def save_note_article(theme: str, article_md: str, output_dir: Path) -> Path:
    """Save Note article to a Markdown file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = theme.replace(" ", "-").replace("　", "-")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = output_dir / f"{ts}_{slug}_note.md"
    path.write_text(article_md, encoding="utf-8")
    logger.info("Saved Note article: %s", path)
    return path


# ---------------------------------------------------------------------------
# Unified output
# ---------------------------------------------------------------------------
def build_unified_output(
    result: ResearchResult,
    x_posts_md: str = "",
    note_md: str = "",
) -> UnifiedOutput:
    """Build a unified output combining all artifacts."""
    return UnifiedOutput(
        theme=result.theme,
        mode=result.mode,
        generated_at=result.researched_at,
        research=result.model_dump(mode="json"),
        x_posts=x_posts_md,
        note_article=note_md,
    )


def save_unified_json(output: UnifiedOutput, output_dir: Path) -> Path:
    """Save unified output as a single JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = output.theme.replace(" ", "-").replace("　", "-")
    ts = output.generated_at.strftime("%Y%m%d-%H%M%S")
    path = output_dir / f"{ts}_{slug}_unified.json"
    path.write_text(
        json.dumps(output.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Saved unified JSON: %s", path)
    return path


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
        description="Gemini API リサーチツール — auto/review 2モード対応",
        usage="python -m pipeline.research <テーマ> [options]",
    )
    parser.add_argument("theme", help="リサーチするテーマ（例: ウイスキー 初心者 おすすめ）")
    parser.add_argument(
        "--mode",
        choices=["auto", "review"],
        default="auto",
        help="モード: auto（自動リサーチ）/ review（体験レビュー＋補足リサーチ）",
    )
    parser.add_argument(
        "--review", "-r",
        dest="user_review",
        default="",
        help="【reviewモード必須】自分の体験レビューテキスト",
    )
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
    parser.add_argument(
        "--x-posts", "-x",
        action="store_true",
        dest="x_posts",
        help="X投稿用テキストも生成",
    )
    parser.add_argument(
        "--note", "-n",
        action="store_true",
        dest="note_article",
        help="Note記事も生成",
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        dest="generate_all",
        help="X投稿 + Note記事を全て生成",
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        dest="json_output",
        help="統合JSONファイルも出力",
    )
    args = parser.parse_args()

    # Validate review mode
    mode = Mode(args.mode)
    if mode == Mode.REVIEW and not args.user_review:
        parser.error("review モードでは --review でレビューテキストを指定してください")

    settings = get_settings()
    if not settings.gemini_api_key:
        logger.error("GEMINI_API_KEY が設定されていません")
        logger.error("  export GEMINI_API_KEY=your-api-key")
        sys.exit(1)

    # --- Research ---
    result = research_theme(
        args.theme,
        gemini_api_key=settings.gemini_api_key,
        model_name=args.model,
        mode=mode,
        user_review=args.user_review,
    )

    from pipeline.config import PROJECT_ROOT
    output_dir = PROJECT_ROOT / args.output
    md_path = save_research(result, output_dir)

    if args.print_output:
        print("\n" + "=" * 60)
        print(result.raw_markdown)
        print("=" * 60)

    print(f"\n✅ リサーチ完了 [{mode.value} mode]: {result.theme}")
    print(f"📄 保存先: {md_path}")

    do_x = args.x_posts or args.generate_all
    do_note = args.note_article or args.generate_all

    x_posts_md = ""
    note_md = ""

    # --- X posts ---
    if do_x:
        x_posts_md = generate_x_posts(
            result,
            gemini_api_key=settings.gemini_api_key,
            model_name=args.model,
        )
        x_path = save_x_posts(result.theme, x_posts_md, output_dir)

        print(f"\n{'─' * 50}")
        print("🐦 X投稿案:")
        print(f"{'─' * 50}")
        print(x_posts_md)
        print(f"{'─' * 50}")
        print(f"📄 保存先: {x_path}")

    # --- Note article ---
    if do_note:
        note_md = generate_note_article(
            result,
            gemini_api_key=settings.gemini_api_key,
            model_name=args.model,
        )
        note_path = save_note_article(result.theme, note_md, output_dir)

        print(f"\n{'─' * 50}")
        print("📝 Note記事:")
        print(f"{'─' * 50}")
        print(note_md)
        print(f"{'─' * 50}")
        print(f"📄 保存先: {note_path}")

    # --- Unified JSON output ---
    if args.json_output:
        unified = build_unified_output(result, x_posts_md, note_md)
        json_path = save_unified_json(unified, output_dir)
        print(f"\n📦 統合JSON: {json_path}")


if __name__ == "__main__":
    main()
