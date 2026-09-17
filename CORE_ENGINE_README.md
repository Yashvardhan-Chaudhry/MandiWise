# MandiWise Core Decision Engine

This bundle is the first runnable implementation of MandiWise. It converts a farmer's crop quantity and dated mandi price observations into a ranked recommendation based on **estimated net realisation**, not the headline modal price.

It intentionally covers the current mid-semester implementation boundary:

- input validation and dated price freshness
- whole-vehicle transport-cost optimisation
- gross revenue, commission, handling, transport and net-realisation calculation
- ranking with a transparent cost breakdown
- automated calculation tests and illustrative demo data

It does **not** yet provide a web UI, user authentication, database persistence, a live scheduled import, or route optimisation. Those are later milestones.

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

The files in `data/` are **illustrative demo/configuration data**, not live AGMARKNET records or legal fee schedules. The production pipeline must replace market prices with cleaned dated imports and must maintain commission/handling/vehicle rates with source notes and effective dates.
