import { test } from "node:test";
import assert from "node:assert/strict";
import { api } from "../src/lib.js";
test("writes send same-origin cookies and the CSRF header", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async (path, options) => {
      assert.equal(path, "/portal/api/logout");
      assert.equal(options.credentials, "same-origin");
      assert.equal(options.headers["X-MandiWise-Request"], "portal");
      assert.equal(options.method, "POST");
      return { ok: true, json: async () => ({ ok: true }) };
    };
    assert.deepEqual(await api("/portal/api/logout", {}), { ok: true });
  } finally {
    globalThis.fetch = original;
  }
});
test("structured validation errors stay visible", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => ({
      ok: false,
      status: 422,
      json: async () => ({
        detail: [
          { loc: ["body", "quantity_quintals"], msg: "Must be positive" },
        ],
      }),
    });
    await assert.rejects(
      api("/test", {}),
      /quantity_quintals: Must be positive/,
    );
  } finally {
    globalThis.fetch = original;
  }
});
