import { z, defineCollection } from "astro:content";

const articles = defineCollection({
  type: "content",
  schema: z.object({
    title: z.string(),
    description: z.string(),
    slug: z.string(),
    articleType: z.enum(["comparison", "spec_analysis", "price_watch"]),
    keyword: z.string(),
    category: z.string().default(""),
    products: z.array(z.string()).default([]),
    createdAt: z.coerce.date(),
    updatedAt: z.coerce.date(),
  }),
});

export const collections = { articles };
