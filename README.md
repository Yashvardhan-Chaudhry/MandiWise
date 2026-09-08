# MandiWise

**AGMARKNET tells a farmer what the price was. MandiWise tells him what reaches his hand — and whether the trip is worth it.**

A decision tool for farmers choosing where to sell. It ranks nearby mandis by **net realisation** — the money left after commission, handling and transport — and finds opportunities to share transport costs with neighbouring farmers.

> **Status:** early development. Architecture is provisional (`docs/ARCHITECTURE.md`, v0.1). Nothing here is settled.

---

## The problem

A farmer with 40 quintals of potato has one question: *where do I sell, and what will I get?*

The Government of India publishes daily prices from every mandi in the country as an open API. That data is good, it's free, and it's available in several languages. **And it still doesn't answer his question** — because the highest price is not the best price.

| 40 quintals of potato | Mandi A (local) | Mandi B (60 km) |
|---|---|---|
| Price per quintal | ₹1,200 | ₹1,380 |
| Gross | ₹48,000 | ₹55,200 |
| Commission | −₹1,920 | −₹2,208 |
| Handling | −₹1,200 | −₹1,200 |
| Transport | −₹3,000 | −₹9,000 |
| **Net** | **₹41,880** | **₹42,792** |

*Illustrative figures.*

An apparent ₹7,200 advantage becomes ₹912 — inside the day's normal price range, and not worth an extra day of travel. **The honest answer is: don't make the trip.** Nothing currently tells him that.

Two structural reasons the gap closes:
- Commission is a **percentage** of sale value, so a higher price means a larger deduction
- Transport is charged **per vehicle**, not per quintal or per kilometre

---

## What it does

**1. Net realisation ranking** — mandis ordered by money that actually reaches the farmer, for his crop, his grade, his quantity, from his village.

**2. Liquidity signal** — whether a mandi has an active market for that crop at all. Sometimes the real choice isn't between two prices; it's between selling elsewhere at a lower price and losing the crop.

**3. Transport pooling** — a tempo carries ~30 quintals, a truck ~100. A farmer with 40 quintals pays for two tempos and uses 60% of the space. Three farmers with 40 each fill a truck. Cost per quintal is a **step function**, and small farmers live permanently on the wrong side of it.

Pooling is **identity-preserved**: we pool the vehicle, never the produce. Each lot stays separately bagged, weighed and auctioned under its own farmer's name, so a premium grade earns a premium price. Costs split proportional to quantity, so nobody subsidises anybody.

---

## Design principles

- **The engine does exact arithmetic.** Core calculations are pure Python with no I/O — deterministic and unit-tested against hand-computed values.
- **Every number is dated and sourced.** No price is shown without its reporting date. Stale data is greyed, never silently substituted.
- **Rates are configuration, not code.** Commission, cess, handling and vehicle rates live in database tables with a source note and effective date.
- **Cache first.** The government API is called on a schedule, never in the request path. A user request never depends on an external service being up.

---

## Deliberately out of scope

- **No price forecasting.** We report dated observations. Prediction on this data would be fabrication.
- **No payments or trading.** This is a pre-transaction decision tool. Trading platforms already exist.
- **No credit, and no attempt to replace the commission agent.** The arhatiya is often the farmer's lender; that relationship is untouched.
- **No dispute resolution.** We record what participants declared. We are not an insurer or an arbitrator.

---

## Users

| Role | What they do |
|---|---|
| **Farmer** | Lists a crop, compares mandis by net return, joins a pool, reviews past decisions |
| **Pool coordinator** | A farmer with elevated permissions — opens a pool, reviews join requests, locks it, arranges transport, records the split |
| **Admin** | Maintains mandi records, rate tables and vehicle rate cards; monitors the nightly data import and data freshness |

---

## Stack

| Layer | Technology |
|---|---|
| Client | React + Vite, multilingual from the first commit |
| API | FastAPI (Python) |
| Core engine | Plain Python — no framework, no I/O, fully testable |
| Database | PostgreSQL |
| Ingestion | Scheduled job pulling the data.gov.in AGMARKNET feed |

---

## Data source

Daily mandi prices are published by the Directorate of Marketing & Inspection through AGMARKNET and made available on [data.gov.in](https://data.gov.in) under India's National Data Sharing and Accessibility Policy.

The feed provides state, district, market, commodity, variety, grade, date, and minimum/maximum/modal prices. It does **not** include arrival quantities or mandi coordinates — the mandi location table is built and maintained by this project. Because the public resource holds only a short rolling window, MandiWise snapshots it nightly and accumulates the price history the API itself does not retain.

---

## Documentation

| File | Contents |
|---|---|
| `docs/ARCHITECTURE.md` | System design, pipeline, entities |
| `docs/DOMAIN.md` | How mandis, commission agents and the deduction stack actually work |
| `docs/DECISIONS.md` | Every decision and why — append-only |
| `docs/IMPROVEMENTS.md` | Backlog |
| `research/` | Data analysis supporting the design |

---

## Team

Built as a Software Engineering group project at Thapar Institute of Engineering & Technology.

## Transport backend

The first transport implementation lives in [`backend/`](backend/README.md):
FastAPI estimates, exact whole-vehicle selection, sourced route/rate configuration,
and persisted coordinator-managed pools. See its README for local setup, a runnable
synthetic demo and API integration. Real transport quotes require separately sourced
rates and distances; the existing price datasets do not provide them.

Dataset review: [`docs/TRANSPORT_DATA_REVIEW.md`](docs/TRANSPORT_DATA_REVIEW.md).
