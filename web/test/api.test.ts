import assert from "node:assert/strict";
import test from "node:test";

import { deleteMaterial, prepareSentenceAudio } from "../src/api.ts";

test("deleteMaterial sends a DELETE request without reading a response body", async () => {
  const calls: Array<{ input: RequestInfo | URL; init: RequestInit | undefined }> = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    calls.push({ input, init });
    return {
      ok: true,
      status: 204,
      json: async () => {
        throw new Error("204 响应不应读取 JSON");
      },
    } as unknown as Response;
  }) as typeof fetch;

  try {
    await deleteMaterial("mat 1/二");
  } finally {
    globalThis.fetch = originalFetch;
  }

  assert.deepEqual(calls, [
    {
      input: "/api/materials/mat%201%2F%E4%BA%8C",
      init: { method: "DELETE" },
    },
  ]);
});

test("prepareSentenceAudio consumes a successful audio response body", async () => {
  let bodyConsumed = false;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async () =>
    ({
      ok: true,
      status: 200,
      arrayBuffer: async () => {
        bodyConsumed = true;
        return new ArrayBuffer(0);
      },
    }) as unknown as Response) as typeof fetch;

  try {
    await prepareSentenceAudio("mat 1", "s/二");
  } finally {
    globalThis.fetch = originalFetch;
  }

  assert.equal(bodyConsumed, true);
});

test("prepareSentenceAudio reports the API detail when preparation fails", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async () =>
    ({
      ok: false,
      status: 503,
      json: async () => ({ detail: "macOS say 暂时不可用。" }),
    }) as unknown as Response) as typeof fetch;

  try {
    await assert.rejects(
      () => prepareSentenceAudio("mat-1", "s1"),
      /macOS say 暂时不可用。/,
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});
