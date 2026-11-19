# MandiWise Core Decision Engine

This bundle is the first runnable implementation of MandiWise. It converts a farmer's crop quantity and dated mandi price observations into a ranked recommendation based on **estimated net realisation**, not the headline modal price.

It intentionally covers the current mid-semester implementation boundary:

- input validation and dated price freshness
- whole-vehicle transport-cost optimisation
- gross revenue, commission, handling, transport and net-realisation calculation
- ranking with a transparent cost breakdown
- automated calculation tests and illustrative demo data

This bundle does **not** provide a web UI, user authentication, database persistence, a live scheduled import, or route optimisation. The first three now exist separately, for transport and pooling, in `backend/` (a FastAPI service with a database and web UI); a live scheduled import and route optimisation are still later milestones.

Per `docs/DECISIONS.md` (2026-09-17), `net_realisation` is to be rebuilt in the canonical engine, `backend/src/mandiwise_transport/engine.py`, adding the `market_fee` term and min/max range this version lacks; that rebuild was done on 2026-11-19 (PR #1, `engine.net_realisation`, exposed via `POST /v1/rankings`), so this bundle is no longer the canonical net-realisation path.

## Quick start

Requires Python 3.11+ and no external packages.

```bash
python3 -m unittest discover -s tests -v
python3 demo.py
```

## Folder map

| Path | Purpose |
| --- | --- |
| `src/mandiwise/models.py` | Validated domain objects and result models. |
| `src/mandiwise/transport.py` | Whole-vehicle least-cost transport calculation. |
| `src/mandiwise/recommendation.py` | Net-realisation calculation, stale-data flag and ranking. |
| `data/vehicle_rates.json` | Configurable illustrative vehicle-rate card. |
| `data/example_market_prices.csv` | Illustrative dated price observations used by the demo. |
| `tests/` | Automated tests that verify the worked project example and edge cases. |
| `docs/MILESTONE_2_3_IMPLEMENTATION.md` | What has been implemented, test evidence and remaining work. |

## Important data note

The two `data/` files this engine reads — `vehicle_rates.json` and `example_market_prices.csv` — are **illustrative demo/configuration data**, not live AGMARKNET records or legal fee schedules. `data/` now also holds real price pulls (AGMARKNET via data.gov.in, `punjab_*.json`, and CEDA historical backfills, `ceda_*.json`); those are read by `mandi_pull.py analyse` and `research/engine_benchmark.py`, not by `demo.py`. The production pipeline must replace market prices with cleaned dated imports and must maintain commission/handling/vehicle rates with source notes and effective dates.
