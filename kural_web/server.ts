import express from "express";
import path from "path";
import dotenv from "dotenv";
import { createServer as createViteServer } from "vite";

dotenv.config();

const app = express();
const PORT = 3000;

app.use(express.json());

// NOTE: This server no longer implements a mock /api/* backend.
//
// The React app talks directly to the real KURAL FastAPI backend
// (see src/lib/api.ts + src/lib/config.ts, configured via VITE_API_BASE_URL)
// for all complaint filing, tracking, and dashboard data. This Express
// server's only job now is to serve the Vite dev bundle / production
// static build — it is intentionally a static/dev host, not an API.

// Vite & Static Asset Handling
async function startServer() {
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Server running on http://0.0.0.0:${PORT} under ${process.env.NODE_ENV || "development"} mode`);
  });
}

startServer();
