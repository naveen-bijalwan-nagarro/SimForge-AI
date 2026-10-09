import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// Vite rejects unknown Host headers (DNS-rebinding protection). Allow Cloudflare quick tunnels, whose
// random *.trycloudflare.com names cannot point at your machine, plus any hosts listed in
// SIMFORGE_ALLOWED_HOSTS (comma-separated; a leading dot allows subdomains, e.g. ".ngrok-free.app").
const allowedHosts = [
  ".trycloudflare.com",
  ...(process.env.SIMFORGE_ALLOWED_HOSTS || "")
    .split(",")
    .map((h) => h.trim())
    .filter(Boolean),
];
export default defineConfig({
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 1600,
    rollupOptions: {
      output: {
        // Separate vendor chunks so each visual library is cached and loaded on demand.
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (/three|@react-three|three-stdlib|troika|camera-controls|maath|meshline/.test(id)) return "vendor-three";
          if (/@deck\.gl|@luma\.gl|@loaders\.gl|@math\.gl|@probe\.gl/.test(id)) return "vendor-deck";
          if (/echarts|zrender/.test(id)) return "vendor-echarts";
          if (/cytoscape|dagre|graphlib/.test(id)) return "vendor-graph";
          return undefined;
        },
      },
    },
  },
  server: {
    port: 5173,
    allowedHosts,
    // scripts/start.ps1 -Dev sets SIMFORGE_API_URL when the API runs on another port.
    proxy: { "/api": { target: process.env.SIMFORGE_API_URL || "http://127.0.0.1:8000", changeOrigin: true } },
  },
  preview: { allowedHosts },
});
