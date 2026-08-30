/// <reference types="vitest/config" />
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

// SPA 构建产物输出到 spa/dist/ (M3 D003: dist 入库, 由后端 FastAPI 托管)
export default defineConfig({
  plugins: [vue()],
  base: "./",
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  test: {
    environment: "jsdom",
    css: true,
    include: ["src/**/__tests__/**/*.spec.ts"],
  },
});
