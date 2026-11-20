/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Static build into site/dist; relative base so the folder works from any path.
export default defineConfig({
  base: "./",
  plugins: [react()],
  build: {
    outDir: "dist",
    target: "es2020",
    assetsInlineLimit: 0,
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/three/")) return "three";
          if (id.includes("@react-three")) return "r3f";
          if (id.includes("framer-motion")) return "motion";
          return undefined;
        },
      },
    },
  },
  server: { port: 5173, strictPort: true },
  // the same Content-Security-Policy as netlify.toml, so `npm run preview` proves the build runs under it
  preview: {
    port: 4173,
    strictPort: true,
    headers: {
      "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; media-src 'self'; worker-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'none'; frame-ancestors 'none'",
    },
  },
  test: { environment: "node", include: ["tests/**/*.test.ts"] },
});
