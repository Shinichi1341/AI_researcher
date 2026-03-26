import { z, defineCollection } from "astro:content";
import { glob } from "astro/loaders";

const articles = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/articles" }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    urlSlug: z.string(),
    articleType: z.enum(["comparison", "spec_analysis", "price_watch", "review"]),
    keyword: z.string(),
    category: z.string().default(""),
    products: z.array(z.string()).default([]),
    rating: z.number().optional(),
    createdAt: z.coerce.date(),
    updatedAt: z.coerce.date(),
  }),
});

export const collections = { articles };
