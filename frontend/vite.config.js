import { defineConfig } from "vite";
const target = process.env.MANDIWISE_API_TARGET || "http://127.0.0.1:8001";
const proxy = Object.fromEntries(
  ["/portal/api", "/v1", "/demo/calculate", "/health"].map((path) => [
    path,
    {
      target,
      changeOrigin: true,
      configure(server) {
        server.on("proxyReq", (out, req) => {
          // Only translate our own local frontend origin. Foreign origins stay foreign.
          if (
            req.headers.origin === "http://127.0.0.1:5173" ||
            req.headers.origin === "http://127.0.0.1:4173"
          )
            out.setHeader("origin", target);
        });
      },
    },
  ]),
);
export default defineConfig({
  resolve: { preserveSymlinks: true },
  server: { proxy },
  preview: { proxy },
});
