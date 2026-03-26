import { defineConfig } from "astro/config";
import tailwind from "@astrojs/tailwind";

export default defineConfig({
  site: "https://shinichi1341.github.io",
  base: "/Drunken_Logic/",
  integrations: [tailwind()],
  markdown: {
    shikiConfig: { theme: "github-dark" },
  },
});
