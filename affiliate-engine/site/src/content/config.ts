import { z, defineCollection } from "astro:content";
import { glob } from "astro/loaders";

/* ─────────────────────────────────────────────
 *  blog コレクション
 *  GitHub Actions (Gemini) が生成する Markdown を
 *  src/content/blog/ に配置し型安全に管理する
 * ───────────────────────────────────────────── */
const blog = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/blog" }),
  schema: z.object({
    /* ── 基本情報 ── */
    title: z.string(),
    description: z.string(),
    urlSlug: z.string(),

    /* ── 記事タイプ ── */
    articleType: z.enum([
      "review",        // レビュー記事
      "comparison",    // 比較記事
      "spec_analysis", // スペック分析
      "price_watch",   // 価格動向
      "tool",          // ツールページ（楽天トレンド検索など）
    ]),

    /* ── 著者区分 (Drunken Logic テンプレート用) ── */
    author: z.enum(["human", "ai", "hybrid"]).default("ai"),

    /* ── SEO / 分類 ── */
    keyword: z.string(),
    category: z.string().default("お酒"),
    tags: z.array(z.string()).default([]),

    /* ── 評価 (Google Rich Results 用) ── */
    rating: z.number().min(1).max(5).optional(),

    /* ── アフィリエイトリンク ── */
    rakutenUrl: z.string().url().optional(),
    amazonUrl: z.string().url().optional(),

    /* ── プロダクト情報 ── */
    products: z.array(z.string()).default([]),
    price: z.string().optional(),        // "5,000円〜6,000円" 等
    brand: z.string().optional(),

    /* ── メディア ── */
    heroImage: z.string().optional(),

    /* ── タイムスタンプ ── */
    createdAt: z.coerce.date(),
    updatedAt: z.coerce.date(),
  }),
});

export const collections = { blog };
