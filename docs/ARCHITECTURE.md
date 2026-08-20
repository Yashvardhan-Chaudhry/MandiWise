# ARCHITECTURE — MandiWise

**Version:** v0.1 — PROVISIONAL
**Status:** Written before implementation. Expect this to change. Nothing here is settled until it has a corresponding entry in `DECISIONS.md`.

---

## 1. What the system does

Given a farmer's location, crop, grade and quantity, MandiWise ranks reachable mandis by **net realisation** — the money that actually reaches him after commission, handling and transport — and identifies opportunities to share transport with nearby farmers selling the same crop in the same window.

Three questions it answers, in priority order:

1. **Where do I get the most money?** — net realisation ranking
2. **Is anyone here even buying my crop?** — liquidity signal
3. **Can I split the truck with someone?** — pooling

---

## 2. Design principles

| Principle | Consequence |
|---|---|
| **The engine does exact arithmetic; nothing guesses.** | Core calculation is deterministic, pure Python, no I/O, no external calls. Fully unit-testable against hand-computed values. |
| **Every number is dated and sourced.** | No price is ever displayed without its reporting date. Stale data is shown greyed, not hidden and not silently substituted. |
| **Rates are configuration, not code.** | Commission percentages, cess, handling charges and vehicle rate cards live in database tables, editable by an admin, each with a source note and effective date. |
| **Cache first, never live at request time.** | The government API is called on a schedule, not in the request path. A user request never depends on an external service being up. |
| **Pool the vehicle, not the produce.** | Lots stay identity-preserved end to end. See §6. |

---

## 3. Layers

### 3.1 Client
React + Vite, deployed to Vercel.

- Internationalisation wired in from the first commit (Punjabi, Hindi, English). Retrofitting i18n is expensive; all user-facing strings go through the translation layer from day one.
- Designed for low-end Android devices: minimal payload, large touch targets, numbers legible without reading dense text.
- Talks to the backend over REST/JSON only. No direct database access, no business logic in the client.

### 3.2 API layer
FastAPI (Python), deployed to a container host.

Responsibilities, and nothing beyond them:
- Request/response validation via Pydantic models
- JWT authentication and role-based permission checks
- Orchestration — calling the engine and the repositories
- Serialisation

**The API layer contains no business arithmetic.** If a calculation lives here instead of in the engine, it has escaped the test suite. That's the rule.

### 3.3 Core engine
Plain Python package. No database access, no HTTP calls, no framework imports. Takes values in, returns values out.

**Three modules:**

**`net_realisation`** — For a given (crop, grade, quantity, origin, candidate mandi), computes:

```
gross            = modal_price × quantity
commission       = gross × commission_rate(state, commodity_class)
market_fee       = gross × fee_rate(state)
handling         = handling_rate_per_quintal × quantity
transport        = vehicle_packing.cost(quantity, distance)
net              = gross − commission − market_fee − handling − transport
```

Returns a net figure plus a **range**, derived from the reported min and max prices — because the modal price is a typical outcome, not a guarantee. The UI shows the range, not a false-precision single number.

**`vehicle_packing`** — The reason this project is non-trivial.

Transport is priced **per vehicle**, not per quintal or per kilometre. Given a quantity and a set of available vehicle classes with capacities, this module solves for the cheapest combination of vehicles that carries the load. Cost per quintal is therefore a **step function**: it jumps sharply when a quantity crosses a capacity boundary and falls as a vehicle fills.

This non-linearity is why small farmers are structurally disadvantaged, and it is the direct mathematical reason pooling works.

**`pool_split`** — Distributes the pooled transport cost across participants, **proportional to quintals contributed**.

Explicitly *not* proportional to sale value. A farmer with premium grade would otherwise subsidise a farmer with poor grade for occupying the same space. Quantity-based splitting is fair, and it is trivially explainable to a user who is being asked to trust it.

### 3.4 Data access
Thin repository layer. SQLAlchemy models and query functions. The engine never imports these; the API layer fetches data and passes plain values into the engine.

### 3.5 Database
PostgreSQL. See §5 for the entities.

---

## 4. Ingestion pipeline

Runs on a schedule, entirely separate from the request path. Writes to the same database the API reads from.

```
data.gov.in API (AGMARKNET daily prices)
        │
        ▼
[1] Fetch — paginated pull, per state, for tracked commodities
        │
        ▼
[2] Validate — reject rows with missing dates, non-numeric prices,
               or a modal price outside the reported min/max
        │
        ▼
[3] Normalise — map commodity and variety names to canonical IDs
                via an alias table; standardise units
        │
        ▼
[4] Upsert — insert or update on (mandi, commodity, variety, grade, date)
        │
        ▼
[5] Derive — recompute liquidity scores (see §7)
        │
        ▼
PostgreSQL  ──►  read by the API layer
```

**Notes**

- The API resource exposes: state, district, market, commodity, variety, grade, arrival_date, min_price, max_price, modal_price. **It does not include arrival quantity** — arrivals volume would require scraping the AGMARKNET portal, which we have deliberately excluded (see `DECISIONS.md`).
- The government resource holds a short rolling window. By snapshotting nightly, **we accumulate a price history the API itself does not provide.** This is an asset, not a workaround.
- Step 3 is the single most underestimated part of this pipeline. Commodity and variety naming is inconsistent across states. Budget real time for the alias dictionary.
- Failures are logged and surfaced on the admin data-health screen. A failed night must be visible, not silent.

---

## 5. Core entities

Provisional. Full ER diagram to follow.

| Entity | Notes |
|---|---|
| `user` | Auth, role, preferred language |
| `farmer_profile` | Village, geocoordinates, landholding |
| `mandi` | Name, APMC, district, state, **geocoordinates** — the government feed has none, so we build and own this table |
| `commodity` / `variety` / `grade` | Canonical reference data |
| `commodity_alias` | Maps messy source names to canonical IDs |
| `price_record` | (mandi, commodity, variety, grade, date, min, max, modal) — one row per reported day |
| `rate_config` | Commission, market fee, handling — keyed by state and commodity class, with source and effective date |
| `vehicle_class` | Capacity in quintals, base rate, per-km rate |
| `distance_matrix` | Precomputed origin→mandi road distances |
| `listing` | A farmer's intent to sell: crop, grade, quantity, ready-by window |
| `pool` | Coordinator, target mandi, date window, state |
| `pool_member` | Listing ↔ pool, with declared quality and allocated cost share |

---

## 6. Pooling: identity-preserved by design

**We pool transport. We do not pool produce.**

Each farmer's lot remains separately bagged, tagged, weighed and auctioned under his own name. Three farmers sharing a truck is three lots in one vehicle, not one blended lot. A premium-grade lot receives a premium-grade price.

This is not a workaround — it mirrors how produce actually moves and is sold.

**Three safeguards address quality and spoilage risk:**

1. **Quality declaration on join.** A farmer states variety, grade and condition when requesting to join a pool. It becomes part of the record.
2. **Coordinator rejection right.** The pool coordinator may decline any join request. A human physically present makes the judgement — the platform does not attempt to assess produce condition remotely.
3. **Quantity-proportional cost split.** Everyone pays for the space they occupy, not the value they carry.

**Explicit limit:** if one member's produce damages another's in transit, MandiWise does not adjudicate. We are not an insurer or an arbitrator. We hold the record of what each member declared; that record is what any dispute would be resolved against. Attempting more would be dishonest about what software can do.

### Pool lifecycle

```
OPEN ──► LOCKED ──► DISPATCHED ──► SETTLED
  │         │
  │         └──► CANCELLED
  └──► CANCELLED
```

- **OPEN** — accepting join requests; aggregate quantity visible against vehicle capacity thresholds
- **LOCKED** — membership frozen, cost split computed, transport assigned
- **DISPATCHED** — consignment has left
- **SETTLED** — outcomes recorded per member

Invalid transitions are rejected in code, not merely discouraged in the UI.

---

## 7. Liquidity signal

The arbitrage case ("sell higher elsewhere") is not the only value the system provides. If a farmer's local mandi has no active market for his crop, his real choice is not between two prices — it is between selling elsewhere at a lower price and losing the crop entirely.

We cannot measure demand directly, because the API does not publish arrival quantities. But **reporting frequency is a usable proxy**:

> For each (mandi, commodity) pair, count reporting days over a trailing 30-day window. Consistent reporting indicates an active market. Sparse or absent reporting indicates there may be no reliable buyer.

Surfaced as a qualitative signal — *active / intermittent / no recent activity* — never as a numeric prediction.

This is computed in ingestion step 5 and stored, not calculated per request.

---

## 8. Distance

The government feed provides no coordinates, and routing APIs have rate limits we do not want in the request path.

**Approach:** precompute an origin→mandi road distance matrix once, using a routing service, and cache it in PostgreSQL. Fall back to great-circle distance multiplied by a road factor for any pair not in the matrix.

Result: accurate, deterministic, and free of any external dependency at demo time.

---

## 9. Deliberately out of scope

Recorded here so it is a decision, not an omission.

| Excluded | Reason |
|---|---|
| Price forecasting | We report dated observations. Prediction on this data would be fabrication. |
| Arrivals volume | Requires scraping AGMARKNET; fragile. Liquidity proxy (§7) covers most of the value. |
| Payments / settlement | We are a pre-transaction decision tool. |
| Replacing the arhatiya | Particularly his lending role. Credit is untouched. |
| Trading / bidding | That is eNAM. Different product. |
| Dispute resolution | See §6. |

---

## 10. Deployment

| Component | Target |
|---|---|
| Client | Vercel |
| API | Container host with a persistent URL |
| Database | Managed PostgreSQL |
| Ingestion | Scheduled CI job — version-controlled, and its run history is itself evidence of a working pipeline |

**Deploy a placeholder to the live URL before any features exist.** Every merge redeploys from there. Leaving deployment until the end is the most common way a project like this fails to submit.

⚠️ Free tiers commonly spin down on inactivity and may pause databases after idle periods. Verify current terms, and test the URL cold before any demo.
