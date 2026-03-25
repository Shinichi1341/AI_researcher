import { defineConfig } from "astro/config";
import tailwind from "@astrojs/tailwind";

export default defineConfig({
  site: "https://your-username.github.io",
  base: "/affiliate-engine",
  integrations: [tailwind()],
  markdown: {
    shikiConfig: { theme: "github-dark" },
  },
});
