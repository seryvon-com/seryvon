import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// No @types/node dependency in this project; declare just what this config needs.
declare const process: { env: Record<string, string | undefined> };

// The FastAPI backend (seryvon.api.main:app) runs on :8000 in dev. The frontend
// calls it through the /api proxy so the same-origin code works unchanged in prod
// behind a reverse proxy.
export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.PORT) || 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
