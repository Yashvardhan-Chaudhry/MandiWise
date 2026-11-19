import { test } from "node:test";
import assert from "node:assert/strict";
import {
  marketRows,
  quintals,
  localeText,
  indiaToday,
  money,
} from "../src/lib.js";
test("market screening preserves valid Punjab rows, rejects wrong state, bad range and low prices", () => {
  const row = {
    state: "Punjab",
    min_price: 100,
    modal_price: 120,
    max_price: 150,
  };
  assert.deepEqual(
    marketRows([
      row,
      { ...row, state: "Haryana" },
      { ...row, max_price: 0 },
      { ...row, modal_price: 20 },
      { ...row, modal_price: "NaN" },
    ]),
    [row],
  );
});
test("display converts kg to quintals, not a relabel", () => {
  assert.equal(quintals(4050), 40.5);
  assert.match(money("1850.00"), /1,850/);
});
test("untranslated locale falls back to English", () => {
  assert.equal(
    localeText({ en: { hello: "Hello" }, hi: {} }, "hi", "hello"),
    "Hello",
  );
  assert.equal(localeText({ en: { hello: "Hello" } }, "ur", "hello"), "Hello");
});
test("Indian calendar day is ISO date suitable for date inputs", () =>
  assert.match(indiaToday(), /^\d{4}-\d{2}-\d{2}$/));
