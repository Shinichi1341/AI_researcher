import { defineConfig } from "astro/config";
import tailwind from "@astrojs/tailwind";

export default defineConfig({
  site: "https://shinichi1341.github.io",
  base: "/AI_researcher/",
  integrations: [tailwind()],
  markdown: {
    shikiConfig: { theme: "github-dark" },
  },
});
