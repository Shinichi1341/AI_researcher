# レビュー → コンテンツ生成パイプライン

`reviews/` にレビューメモを置き、CLIで実行するとリサーチ・X投稿・Note記事を一括生成します。

---

## 1. レビューメモの書き方

```markdown
---
keyword: クラフトジン 〇〇
category: お酒
rating: 4.0
---
ここに自分のレビューを書く。箇条書きでも文章でもOK。
```

| フィールド | 必須 | 説明 |
|-----------|------|------|
| keyword   | ○   | 商品名やキーワード（リサーチ・SEOに使用） |
| category  | △   | カテゴリ（デフォルト: "お酒"） |
| rating    | △   | 自分の評価 1.0〜5.0 |

ファイル名は自由（例: `craft-gin-roku.md`）。

---

## 2. モード説明

### Auto モード（自動リサーチ）

Gemini がテーマを完全自動でリサーチし、コンテンツを生成。
自分のレビューがない商品や、市場調査目的で使う。

### Review モード（体験レビュー主軸）

**自分のレビューが最優先で扱われる。** Gemini は補足役。

| 生成物 | レビューの扱い |
|--------|---------------|
| リサーチ | レビューから要点を抽出 → 世間の評価と比較 → 補足情報追加（原文は改変しない） |
| X投稿 | レビューの体験エピソードを必ず含む一人称の投稿文 |
| Note記事 | レビューの言葉をそのまま活かし、補足リサーチは裏付けとして自然に織り込む |

---

## 3. 使い方

### 基本コマンド

```bash
# ワークスペース直下から入る場合
cd affiliate-engine

# 以降は affiliate-engine/ 配下で実行する
source .venv/bin/activate
```

`pipeline.research` は `affiliate-engine/` 配下で実行する必要があります。
ワークスペース直下 (`/home/ymc-katayama/work/sub_work`) でそのまま実行すると、
`reviews/...` も `pipeline.research` も見つかりません。

環境を切り替えずに実行したい場合は、`.venv/bin/python` を直接使ってください。

### Auto モード（レビューなし）

```bash
# リサーチのみ
.venv/bin/python -m pipeline.research "山崎12年" --mode auto

# リサーチ + X投稿 + Note記事 + 統合JSON
.venv/bin/python -m pipeline.research "山崎12年" --mode auto -a --json
```

### Review モード（レビューあり）

```bash
# レビューファイルの内容を渡す方法
.venv/bin/python -m pipeline.research "アードベッグ10年" --mode review \
  --review "$(cat reviews/craft-gin-roku.md)" -a --json

# 直接テキストを渡す方法
.venv/bin/python -m pipeline.research "アードベッグ10年" --mode review \
  --review "最初の感想は正露丸。ピートが強烈だが飲み方で印象が変わる..." \
  -a --json
```

ワークスペース直下から 1 行で実行するならこちらです。

```bash
cd affiliate-engine && .venv/bin/python -m pipeline.research "アードベッグ10年" --mode review \
  --review "$(cat reviews/craft-gin-roku.md)" -a --json
```

### オプション一覧

| フラグ | 短縮 | 説明 |
|--------|------|------|
| `--mode auto\|review` | — | auto: 自動リサーチ / review: 体験レビュー＋補足 |
| `--review "テキスト"` | `-r` | review モード時の体験レビュー（必須） |
| `--x-posts` | `-x` | X投稿を生成 |
| `--note` | `-n` | Note記事を生成 |
| `--all` | `-a` | X投稿 + Note記事を全て生成 |
| `--json` | `-j` | 統合JSONも出力 |
| `--print` | `-p` | リサーチ結果を標準出力に表示 |
| `--output DIR` | `-o` | 出力先（デフォルト: `data/research/`） |
| `--model NAME` | `-m` | Gemini モデル名（デフォルト: `gemini-2.5-flash`） |

---

## 4. 出力ファイル

`data/research/` に以下が生成される：

```
data/research/
  20260326-223000_アードベッグ10年.md          # リサーチ結果
  20260326-223000_アードベッグ10年.json         # リサーチJSON
  20260326-223015_アードベッグ10年_x-posts.md   # X投稿案 ×3
  20260326-223030_アードベッグ10年_note.md      # Note記事
  20260326-223030_アードベッグ10年_unified.json  # 統合JSON（--json時）
```

### 統合JSON構造（`--json` 時）

```json
{
  "theme": "アードベッグ10年",
  "mode": "review",
  "generated_at": "2026-03-26T22:30:30",
  "research": {
    "theme": "...",
    "mode": "review",
    "raw_markdown": "...(リサーチ結果)...",
    "user_review": "...(あなたのレビュー原文)..."
  },
  "x_posts": "...(X投稿3パターン)...",
  "note_article": "...(Note記事全文)..."
}
```

---

## 5. ワークフロー例

```
1. reviews/ にメモを書く
2. cd affiliate-engine && .venv/bin/python -m pipeline.research "テーマ" --mode review -r "$(cat reviews/xxx.md)" -a --json
3. X投稿案をそのままXに投稿
4. Note記事をコピーしてNoteに投稿
5. アフィリエイトリンクを手動で追加
```

---

## 環境変数

```bash
export GEMINI_API_KEY=your-api-key
```
