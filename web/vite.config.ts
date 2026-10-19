import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Alles wird mitgebündelt. Kein CDN, keine Schrift von fremden Servern —
// sonst zeigt die Seite ohne Internet nichts, und genau das war der Zustand
// vorher. Bei einer KI, die "läuft komplett bei dir" verspricht, ist das
// nicht bloß unschön.

// Backend für den Entwicklungsserver: XERA_BACKEND=http://adresse:8000 npm run dev
const BACKEND = process.env.XERA_BACKEND ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  base: "/app/",
  build: {
    outDir: "dist",
    assetsDir: "mittel",
    // Der Kern ändert sich selten, die Oberfläche oft. Getrennt heißt: nach
    // einer Änderung lädt der Browser nur den kleinen Teil neu.
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom"],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: BACKEND, changeOrigin: true },
      "/auth": { target: BACKEND, changeOrigin: true },
    },
  },
});
