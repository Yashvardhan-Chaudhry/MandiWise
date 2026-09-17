# Mid-Semester Implementation Evidence

## Implemented now

The core engine is implemented as pure Python with no database, network or UI dependency. It can therefore be checked against hand-worked figures and tested repeatedly.

### Recommendation formula

For each eligible mandi:

```text
gross revenue       = modal price per quintal x farmer quantity
commission          = gross revenue x configurable commission rate
handling            = handling charge per quintal x farmer quantity
transport           = least-cost whole-vehicle combination for quantity and distance
net realisation     = gross - commission - handling - transport
```

Mandi offers are ranked by net realisation, descending. A stale observation is retained with an explicit warning flag; it is never presented as current.

### Transport rules

- Vehicles are whole units. The engine never bills a fractional tempo or truck.
- It finds the least-cost feasible vehicle combination from the configured rate card.

Pooling is a separate team module and is deliberately not included in this bundle to avoid overlapping implementation work.

## Verification evidence

`python3 -m unittest discover -s tests -v` validates:

1. The PDF/README illustrative 40-quintal comparison: INR 41,880 local and INR 42,792 distant.
2. A higher displayed price can rank below a lower-price mandi after transport.
3. Zero quantity is rejected.
4. Old price observations are visibly flagged as stale.

## Data boundary

`example_market_prices.csv` and `vehicle_rates.json` are marked illustrative. The completed ingestion module must replace price rows with cleaned, dated AGMARKNET data. Production rate cards require an admin-maintained source reference and effective date.

## Remaining milestones

1. Persist cleaned market data, mandi locations and rate cards in PostgreSQL.
2. Expose this engine through FastAPI endpoints.
3. Build farmer, coordinator and administrator interfaces in React with Punjabi, Hindi and English text.
4. Integrate the separate pooling module, authentication, scheduled import monitoring and end-to-end testing.
