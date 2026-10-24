import type { Config } from "@react-router/dev/config";

export default {
  // Операторский пульт: всё состояние живое и опрашивается с клиента, SSR не нужен.
  // Собирается статика в build/client, её раздаёт nginx и проксирует /api на бэкенд.
  ssr: false,
  buildDirectory: "build",
} satisfies Config;
