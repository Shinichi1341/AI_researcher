import { defineConfig } from "astro/config";
import tailwind from "@astrojs/tailwind";
import sitemap from "@astrojs/sitemap";
import vercel from "@astrojs/vercel";

export default defineConfig({
  site: "https://drunken-logic.vercel.app",
  output: "static",
  adapter: vercel(),
  integrations: [tailwind(), sitemap()],
  markdown: {
    shikiConfig: { theme: "github-dark" },
  },
});
