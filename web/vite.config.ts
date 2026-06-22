import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The FastAPI backend (seryvon.api.main:app) runs on :8000 in dev. The frontend
// calls it through the /api proxy so the same-origin code works unchanged in prod
// behind a reverse proxy.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
