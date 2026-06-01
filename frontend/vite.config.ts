import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        // Fusion resume generate can run several minutes (SSE stream).
        timeout: 0,
        proxyTimeout: 0,
      },
    },
  },
});
