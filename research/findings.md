# Findings

Data validation against the AGMARKNET feed, for commodities around Patiala. Not yet run — see claude.md, "The data validation, when it runs."

---

## 1. Price spread

**Method:** For each commodity-day across 6–8 mandis within ~100 km, compute `(max modal − min modal) / min modal`. Plot the distribution over 30 days.

**Reads as:**
- \>10% — strong case for the arbitrage claim
- 4–10% — conditional; the claim needs adjusting
- <3% — arbitrage story fails; pivot toward liquidity and pooling

**Results:** _(pending — no pull has been run yet)_

---

## 2. Liquidity

**Method:** For each (mandi, commodity) pair, count reporting days in a trailing 30-day window.

**Reads as:** Consistent reporting = active market. Sparse reporting = no reliable buyer.

**Results:** _(pending — no pull has been run yet)_

---

## Raw pull

Not yet retained. To be added here, dated, once the validation runs.
