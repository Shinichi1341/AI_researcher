# Drunken Logic — フロントマター仕様書

GitHub Actions (Gemini) が Markdown 記事を生成する際に準拠すべきフロントマター定義。
`src/content/blog/` に配置される各 `.md` ファイルの先頭に YAML 形式で記述する。

---

## 必須フィールド

| フィールド     | 型                  | 説明                                        | 例                                      |
| -------------- | ------------------- | ------------------------------------------- | --------------------------------------- |
| `title`        | `string`            | 記事タイトル。SEO を意識した 40–60 文字推奨  | `【正直レビュー】アードベッグ10年`       |
| `description`  | `string`            | meta description。120–160 文字              | `強烈なピート香と奥深い魅力を徹底解説`   |
| `urlSlug`      | `string`            | URL パス（英数字 + ハイフン）               | `ardbeg-10-year-review`                  |
| `articleType`  | `enum`              | `review` / `comparison` / `spec_analysis` / `price_watch` / `tool` | `review` |
| `keyword`      | `string`            | 主要検索キーワード                          | `アードベッグ 10年 レビュー`             |
| `createdAt`    | `datetime (ISO8601)` | 作成日時                                    | `2026-03-26T18:06:56`                   |
| `updatedAt`    | `datetime (ISO8601)` | 最終更新日時                                | `2026-03-26T18:06:56`                   |

## オプションフィールド

| フィールド     | 型              | デフォルト | 説明                                           | 例                                             |
| -------------- | --------------- | ---------- | ---------------------------------------------- | ---------------------------------------------- |
| `author`       | `enum`          | `"ai"`     | `human` / `ai` / `hybrid`（Drunken Logic テンプレート）| `hybrid`                                  |
| `category`     | `string`        | `"お酒"`   | カテゴリ                                       | `ウイスキー`                                   |
| `tags`         | `string[]`      | `[]`       | タグ（SEO・フィルタ用）                        | `["ウイスキー", "アイラ", "ピート"]`           |
| `rating`       | `number`        | —          | 1–5（0.5 刻み）。Google リッチリザルト用       | `4.5`                                          |
| `rakutenUrl`   | `string (URL)`  | —          | 楽天アフィリエイト URL                         | `https://item.rakuten.co.jp/...`               |
| `amazonUrl`    | `string (URL)`  | —          | Amazon アソシエイト URL                        | `https://www.amazon.co.jp/dp/...`              |
| `products`     | `string[]`      | `[]`       | 関連プロダクト名リスト                         | `["アードベッグ10年"]`                          |
| `price`        | `string`        | —          | 参考価格レンジ                                 | `"5,000円〜6,000円"`                            |
| `brand`        | `string`        | —          | ブランド名                                     | `アードベッグ`                                  |
| `heroImage`    | `string`        | —          | ヒーロー画像パス（public 内の相対パス）        | `/images/ardbeg-10.webp`                        |

---

## テンプレート例

### レビュー記事 (review)

```yaml
---
title: "【正直レビュー】アードベッグ10年：強烈なピート香と奥深い魅力"
description: "ウイスキー愛好家を魅了するアイラモルトの代表格、アードベッグ10年を徹底レビュー。"
urlSlug: "ardbeg-10-year-review"
articleType: "review"
author: "hybrid"
keyword: "アードベッグ 10年 レビュー"
category: "ウイスキー"
tags: ["ウイスキー", "スコッチ", "アイラ", "ピート"]
rating: 4.5
rakutenUrl: "https://item.rakuten.co.jp/example/ardbeg10/"
amazonUrl: "https://www.amazon.co.jp/dp/B00EXAMPLE"
products: ["アードベッグ10年"]
price: "5,000円〜6,000円"
brand: "アードベッグ"
createdAt: "2026-03-26T18:06:56"
updatedAt: "2026-03-26T18:06:56"
---
```

### 比較記事 (comparison)

```yaml
---
title: "【2026年版】アイラウイスキー5選 徹底比較"
description: "ラフロイグ、アードベッグ、ボウモア…アイラの名門を飲み比べ。データと実体験で比較します。"
urlSlug: "islay-whisky-comparison-2026"
articleType: "comparison"
author: "ai"
keyword: "アイラウイスキー 比較 おすすめ"
category: "ウイスキー"
tags: ["ウイスキー", "比較", "アイラ"]
products: ["アードベッグ10年", "ラフロイグ10年", "ボウモア12年"]
createdAt: "2026-03-26T12:00:00"
updatedAt: "2026-03-26T12:00:00"
---
```

### ツールページ (tool)

```yaml
---
title: "お酒トレンド検索 — 楽天 API リアルタイム比較"
description: "楽天 API を活用してお酒のトレンド・価格を検索・比較できるツールです。"
urlSlug: "sake-trend-search"
articleType: "tool"
author: "ai"
keyword: "お酒 トレンド 検索 比較"
category: "ツール"
tags: ["ツール", "楽天", "トレンド"]
createdAt: "2026-03-26T12:00:00"
updatedAt: "2026-03-26T12:00:00"
---
```

---

## Gemini プロンプト用コピペチャンク

以下を Gemini のシステムプロンプトに含めることで、正しいフロントマターの生成を保証する:

```
あなたは「Drunken Logic」というお酒レビューサイトの記事を生成します。
Markdown ファイルの先頭に以下の YAML フロントマターを **必ず** 含めてください。

必須: title, description, urlSlug, articleType, keyword, createdAt, updatedAt
任意: author(default:ai), category(default:お酒), tags, rating(1-5, 0.5刻み),
      rakutenUrl, amazonUrl, products, price, brand, heroImage

rating は articleType が "review" の場合に必ず含めてください（Google リッチリザルト用）。
urlSlug は英数字とハイフンのみで構成してください。
日時は ISO 8601 形式で出力してください。
```

---

## 記事本文の構成テンプレート（Gemini 用）

Gemini に記事を生成させる際は、以下の構成ルールも含めてください。

```
# ライティングルール
- 1文は60文字以内
- 2〜3文ごとに改行
- セクションごとに見出し（H2/H3）を付ける
- 箇条書きを積極的に使う
- "結論→理由→具体例"の順で書く
- 冗長な説明は禁止
- 主観（体験）と客観（一般評価）を明確に分ける
- 専門用語は簡潔に解説する

# レビュー記事の構成（必須セクション）

## 導入文（共感＋結論）
結論を最初に箇条書き3つで。

## 基本情報
表形式で商品スペックを整理。

## 正直レビュー（体験ベース）
<div class="review-voice"> で囲む。
### 第一印象
### 香り
### 味わい
### 飲み方別レビュー
（箇条書きで：ハイボール / ロック / 水割り / ストレート）

## 一般的な評価（客観データ）
受賞歴と風味特徴を箇条書きで整理。

## メリット・デメリット
### ✅ メリット（3〜4個）
### ❌ デメリット（2〜3個）

## 向いている人（絵文字 + 箇条書き）

## おすすめの飲み方・ペアリング
飲み方は表形式。ペアリングは箇条書き。

## 価格と購入方法
参考価格と購入チャネルを案内。

## まとめ（CTA）
結論を3行で。購入への自然な導線。
```
