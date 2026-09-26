import assert from "node:assert/strict";
import { unlink, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import test from "node:test";

import viteConfig, { apiProxyTarget } from "../vite.config.ts";

test("Vite 从仓库根目录加载 API 地址，且进程环境优先", async () => {
  assert.equal(typeof viteConfig, "function");

  const mode = `vite-config-${process.pid}`;
  const envFile = resolve(import.meta.dirname, `../../.env.${mode}`);
  const previousApiUrl = process.env.READ_ALONG_API_URL;

  await writeFile(envFile, "READ_ALONG_API_URL=http://root-env.example:8765\n", "utf8");
  delete process.env.READ_ALONG_API_URL;

  try {
    const fileConfig = await viteConfig({ command: "serve", mode });
    assert.equal(fileConfig.server?.proxy?.["/api"], "http://root-env.example:8765");

    process.env.READ_ALONG_API_URL = "https://process-env.example:9443";
    const processConfig = await viteConfig({ command: "serve", mode });
    assert.equal(processConfig.server?.proxy?.["/api"], "https://process-env.example:9443");
  } finally {
    await unlink(envFile);
    if (previousApiUrl === undefined) {
      delete process.env.READ_ALONG_API_URL;
    } else {
      process.env.READ_ALONG_API_URL = previousApiUrl;
    }
  }
});

test("API 地址必须存在且是 HTTP(S) 绝对 URL", () => {
  for (const value of [undefined, "", " ", "/api", "localhost:8765", "ftp://example.com"]) {
    assert.throws(() => apiProxyTarget(value), /READ_ALONG_API_URL/);
  }

  assert.equal(apiProxyTarget("http://127.0.0.1:8765"), "http://127.0.0.1:8765");
  assert.equal(apiProxyTarget("https://api.example.com/base"), "https://api.example.com/base");
});
