import assert from "node:assert/strict";
import test from "node:test";

import {
  clearMaterialAudioCache,
  deleteMaterial,
  prepareSentenceAudio,
  sentenceAudioUrl,
} from "../src/api.ts";

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

test("clearMaterialAudioCache clears a material audio cache without reading a response body", async () => {
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
    await clearMaterialAudioCache("mat 1/二");
  } finally {
    globalThis.fetch = originalFetch;
  }

  assert.deepEqual(calls, [
    {
      input: "/api/materials/mat%201%2F%E4%BA%8C/audio-cache",
      init: { method: "DELETE" },
    },
  ]);
});

test("prepareSentenceAudio consumes a successful audio response body and returns duration", async () => {
  let bodyConsumed = false;
  let requestedUrl: RequestInfo | URL | undefined;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    requestedUrl = input;
    return {
      ok: true,
      status: 200,
      headers: new Headers({ "X-Read-Along-Audio-Duration-Seconds": "1.5" }),
      arrayBuffer: async () => {
        bodyConsumed = true;
        return new ArrayBuffer(0);
      },
    } as unknown as Response;
  }) as typeof fetch;

  try {
    const duration = await prepareSentenceAudio("mat 1", "s/二");
    assert.equal(duration, 1.5);
  } finally {
    globalThis.fetch = originalFetch;
  }

  assert.equal(bodyConsumed, true);
  assert.equal(requestedUrl, "/api/materials/mat%201/sentences/s%2F%E4%BA%8C/audio");
});

test("prepareSentenceAudio can bypass stale browser audio cache", async () => {
  let requestedUrl: RequestInfo | URL | undefined;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    requestedUrl = input;
    return {
      ok: true,
      status: 200,
      headers: new Headers(),
      arrayBuffer: async () => new ArrayBuffer(0),
    } as unknown as Response;
  }) as typeof fetch;

  try {
    await prepareSentenceAudio("mat 1", "s/二", "repair 1");
  } finally {
    globalThis.fetch = originalFetch;
  }

  assert.equal(
    requestedUrl,
    "/api/materials/mat%201/sentences/s%2F%E4%BA%8C/audio?reload=repair+1",
  );
});

test("sentenceAudioUrl encodes material and sentence identities", () => {
  assert.equal(
    sentenceAudioUrl("mat-1", "sentence-1"),
    "/api/materials/mat-1/sentences/sentence-1/audio",
  );
});

test("sentenceAudioUrl appends a reload token when provided", () => {
  assert.equal(
    sentenceAudioUrl("mat 1", "sentence/1", "repair 1"),
    "/api/materials/mat%201/sentences/sentence%2F1/audio?reload=repair+1",
  );
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
