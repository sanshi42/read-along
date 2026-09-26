import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

const repositoryRoot = decodeURIComponent(new URL("..", import.meta.url).pathname);

export function apiProxyTarget(value: string | undefined): string {
  if (!value) {
    throw new Error("缺少必填配置 READ_ALONG_API_URL。");
  }

  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error("READ_ALONG_API_URL 必须是 HTTP(S) 绝对 URL。");
  }

  if ((url.protocol !== "http:" && url.protocol !== "https:") || !url.host) {
    throw new Error("READ_ALONG_API_URL 必须是 HTTP(S) 绝对 URL。");
  }

  return value;
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, repositoryRoot, "READ_ALONG_API_URL");

  return {
    plugins: [react()],
    server: {
      proxy: {
        "/api": apiProxyTarget(env.READ_ALONG_API_URL),
      },
    },
  };
});
