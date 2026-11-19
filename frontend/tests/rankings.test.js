import { test } from "node:test";
import assert from "node:assert/strict";
import { candidateMarkets } from "../src/lib.js";

test("ranking candidates preserve same-name mandis in different districts without duplicating varieties", () => {
  const row = {
    state: "Punjab",
    market: "Same APMC",
    district: "Patiala",
    variety: "Local",
  };
  const markets = candidateMarkets([
    row,
    { ...row, variety: "Other" },
    { ...row, district: "Ludhiana" },
    { ...row, state: "Haryana" },
  ]);
  assert.equal(markets.length, 2);
  assert.notEqual(markets[0].id, markets[1].id);
  assert.deepEqual(
    markets.map((m) => m.district),
    ["Patiala", "Ludhiana"],
  );
});
