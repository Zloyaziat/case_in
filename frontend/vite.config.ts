import { fileURLToPath } from "node:url";

import { reactRouter } from "@react-router/dev/vite";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

// В разработке API отдаёт бэкенд на :8000 (uvicorn app.main:app --reload).
// Прокси убирает CORS и позволяет фронту ходить по относительным /api/... —
// ровно так же, как это делает nginx в контейнере.
const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [tailwindcss(), reactRouter()],
  resolve: {
    // tsconfig paths ("~/*" -> "./app/*") дев-сервер не читает — дублируем alias
    alias: [
      {
        find: /^~\//,
        replacement: `${fileURLToPath(new URL("./app", import.meta.url))}/`,
      },
    ],
  },
  server: {
    port: 3000,
    proxy: {
      "/api": { target: BACKEND, changeOrigin: true },
    },
  },
});
