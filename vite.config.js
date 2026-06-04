import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import svgr from "vite-plugin-svgr";

export default defineConfig({
  // Import any SVG as a React component via `import X from "./x.svg?react"`.
  plugins: [react(), svgr()],
});
