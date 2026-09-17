# Findings

Data validation for the two measurements defined in `claude.md`. **Run 2026-09-17.**

> **Headline:** the price-spread hypothesis holds, and holds strongly — median
> dispersion of **73.1%** across 2,821 same-day cross-sections. Open risk #1 in
> `claude.md` ("the core claim is unverified") is now tested. Read the caveats
> before treating it as settled: this measures **gross** spread, not net realisation.

---

## What was measured, and against what

| | |
|---|---|
| **Historical corpus** | 16,907 rows, **2023-10-02 → 2025-10-30**, Patiala district: 7 mandis (Dudhansadhan, Ghanaur, Nabha, Patiala, Patran, Rajpura, Samana) × 8 commodities (potato, onion, tomato, green chilli, brinjal, cauliflower, bhindi, cucumber). 92% also carry arrival volumes. |
| **Live corpus** | 836 rows, 50 Punjab mandis, 2 days: **2026-09-04** and **2026-09-07**. |
| **Sources** | Historical: CEDA (see attribution below). Live: `data.gov.in` AGMARKNET resource `9ef84268-d588-465a-a308-a864a43d0070`. |
| **Raw data retained** | Yes — `data/*.json`, committed. |
| **Reproduce** | `python mandi_pull.py analyse` |

The two corpora cover **disjoint time windows** and are never compared against each
other. Grades differ between sources (CEDA carries none), and grade is part of the
grouping key, so cross-source contamination is structurally impossible.

---

## 1. Price spread

**Method** (as specified in `claude.md`): for each commodity-day, across mandis
reporting the *same* commodity, variety and grade, compute
`(max modal − min modal) / min modal`. Groups with fewer than 3 reporting mandis are
discarded as too thin for a cross-section.

### Result

| Statistic | Value |
|---|---|
| Comparable groups | **2,821** |
| 25th percentile | 46.7% |
| **Median dispersion** | **73.1%** |
| 75th percentile | 113.9% |

**Verdict: STRONG.** `claude.md` reads >10% as strong, 4–10% as conditional, <3% as
failure. The median is 73.1% and even the 25th percentile is 46.7% — the entire
interquartile range sits far above the strong threshold. This is not one lucky day:
it is 2,821 independent same-day cross-sections over two years.

### What this does and does not establish

- ✅ **Prices across nearby mandis do not cluster.** The premise the product rests on
  is real and large.
- ❌ **It does not prove net-positive arbitrage.** This is a *gross* price spread.
  The product's actual claim is that a farther mandi nets more *after* commission,
  market fee, handling and transport. A 73% median spread is a wide cushion for
  those costs, but the cushion has not been tested against real rates — and
  `claude.md` open risk #2 (transport rates unsourced) is still open. **The
  `net_realisation` engine, fed with sourced rates, is what would close this.**
- ⚠️ **Radius is tighter than the product assumes.** The historical comparisons are
  *within Patiala district* (7 mandis), against the ~100 km radius the product
  targets. This most likely makes the figure **conservative** — a wider radius would
  tend to widen spreads, not narrow them — but that is an expectation, not a
  measurement.

---

## 2. Liquidity

**Method** (as specified in `claude.md`): for each (mandi, commodity), count
reporting days in a trailing 30-day window. Consistent reporting indicates an active
market; sparse reporting indicates no reliable buyer.

### Result — historical corpus, window 2025-10-01 → 2025-10-30

The corpus observed all 30 days of this window, so the denominator is a full 30.

| | |
|---|---|
| Market-commodity pairs | 45 |
| **Median reporting days** | **21 of 30** |
| 25th / 75th percentile | 16 / 23 |
| Active (≥60% of days) | 27 pairs |
| Intermittent (20–60%) | 17 pairs |
| Sparse (<20%) | 1 pair |

Most pairs trade most days, but **40% are intermittent or worse** — meaning "is
anyone here buying my crop this week" is a genuinely separate question from "where is
the price highest", exactly as `docs/ARCHITECTURE.md` §7 argues. The liquidity signal
earns its place independently of the spread result.

The 60% / 20% bucket cut-offs are a **provisional reading aid, not a sourced
threshold.** Nothing in the project defines them yet; they should be set deliberately
before they reach a user-facing signal.

### Live corpus — not yet measurable

Only 2 days have been captured (2026-09-04, 2026-09-07), so at most 2 of 30 window
days are observed. 597 pairs exist but no liquidity judgement is possible from two
days. **This needs daily pulls to accumulate**; it is not a result.

---

## Data quality findings

These emerged from the validation and matter for the ingestion pipeline:

1. **One mandi emits placeholder prices, persistently.** Patti APMC reported modal
   prices of ₹0.08–₹32.90 on *both* live pull days (11 rows, then 12) against real
   prices starting near ₹200. Not a one-off glitch — a recurring, mandi-specific
   reporting fault. A ₹50 floor rejects and logs them (see `docs/DECISIONS.md`).
   Without it, dispersion inflated to a meaningless *3,807,900%*.
2. **~30% of commodity names disagree between the two sources.** Full analysis in
   `research/commodity_aliases.md`. Two names could not be mapped and were left
   unmapped rather than guessed.
3. **The live feed carries mixed-script names** (one row contains Devanagari), which
   breaks any pipeline assuming ASCII.
4. **The historical source stops at ~2025-10-30.** It is a research/backfill source;
   `data.gov.in` remains the only current feed. See `docs/DECISIONS.md` for the
   verified API contract behind both pullers.

---

## What this changes

- **Open risk #1 is addressed** for gross spread, and should be re-stated in
  `claude.md` as "premise validated; net realisation still unproven" rather than
  closed outright.
- **Open risk #2 (transport rates) is now the blocking unknown.** The spread result
  makes the product plausible; only sourced rates can make it *true*.
- The pivot contingency in `claude.md` ("if the spread comes back weak, the product
  pivots toward liquidity and pooling") is **not** triggered.

---

## Attribution

Historical data: **CEDA Agri Market Data (CEDA-AMD), 2000-2023. Centre for Economic
Data & Analysis, Ashoka University** — free for non-commercial use; their logo is
required on published visuals derived from it. Live data: AGMARKNET via
`data.gov.in`, Ministry of Agriculture & Farmers Welfare.
