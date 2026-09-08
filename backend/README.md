# MandiWise transport backend

Version 0.1: transport estimates and coordinator-managed pooling. Runs independently
today and can be integrated into the future MandiWise API. It does not need a live
government API call to serve a request.

## Included

- FastAPI endpoints with Swagger at `/docs` and OpenAPI at `/openapi.json`.
- Exact whole-vehicle cost optimisation; fractional quintals supported to 0.01 q (1 kg).
- Pool estimates showing **each participant's cost and savings** against their solo trip.
- Sourced, dated, route-specific rate cards and directed road-distance records.
- Persisted pools, join approval, withdrawal/rejoin, capacity checks, immutable locked quotes,
  dispatch and outcome records, and coordinator audit events.
- Signed, expiring bearer tokens; roles loaded from the database rather than trusted from a request.
- SQLite for local development, PostgreSQL via SQLAlchemy and an Alembic migration.
- An idempotent mandi catalogue import from the committed Punjab snapshots.

## Quick start (Python 3.12+, PowerShell)

Run from this `backend` directory. Install [uv](https://docs.astral.sh/uv/getting-started/installation/)
if needed, or use the pip alternative below.

```powershell
uv sync --frozen --extra test
$env:JWT_SECRET = uv run python -c "import secrets; print(secrets.token_urlsafe(48))"
$env:DATABASE_URL = 'sqlite:///./transport.db'
uv run alembic upgrade head
uv run mandiwise-transport seed-markets --data-dir ../data
uv run uvicorn mandiwise_transport.api:create_app --factory --host 127.0.0.1 --port 8000
```

Keep the secret stable between restarts if existing tokens should continue to work.
There is no default secret and no unauthenticated signup/token endpoint. Never commit
your secret, tokens, database, or real transport contact details to Git.

Pip alternative: `python -m venv .venv`, activate it, `python -m pip install -e '.[test]'`,
then run the same commands without `uv run`. The checked-in `uv.lock` is the reproducible path.

## First users and a working example

In another terminal with the **same** DATABASE_URL and JWT_SECRET:

```powershell
uv run mandiwise-transport create-user --name 'Local admin' --role admin
uv run mandiwise-transport token <returned-user-id>
```

Use the returned token in Swagger's **Authorize** dialog or as `Authorization: Bearer TOKEN`.
The CLI issues one-hour tokens by default; `--hours 24` is the maximum CLI lifetime.
Create farmer and coordinator accounts the same way. A coordinator is a farmer with
pool-management permission and can also join a pool. Administrators manage reference
data; they cannot act as another coordinator or view participants' lots.

For a repeatable, complete example against the running API:

```powershell
uv run python scripts/demo_client.py
```

This local development script provisions its own three users through the local
database, then calls the real HTTP API to create **clearly labelled synthetic**
locations/rates, quote, join, approve, lock, dispatch and settle a demonstration pool.
It requires the server's database and secret. Run only on a development database.
No demo configuration is installed automatically on application startup.

## Transport inputs and units

1. An admin creates a pickup `origin` and a destination `mandi`, or imports mandi names.
2. Create a directed route with sourced road distance and its validity dates.
3. Create a rate card for that same origin/destination with sourced prices and validity dates.
4. Request a quote with both IDs, a travel date, and quantity.

```json
{
  "route_id": "returned-route-id",
  "rate_card_id": "returned-card-id",
  "travel_date": "2026-09-15",
  "quantity_quintals": "40.00"
}
```

Send this to `POST /v1/transport/quote`. Dates in examples must fall within your own
configured validity window. All travel-date checks use Asia/Kolkata, not server-local time.

Each vehicle type has `code`, `capacity_quintals`, `base_cost_inr`, and `per_km_inr`.
Its trip cost is `base_cost_inr + per_km_inr × distance_km`. Round once per vehicle
to the nearest paisa (half up), then optimise the whole fleet. Configure an agreed
flat trip quote as the base with a zero per-km component. Rates must include whatever
return travel, tolls, loading or other charges the supplier agreed; the engine does
not invent those charges. Do not charge them again when integrating net realisation.

Money is returned as decimal strings (INR), plus total integer paise. Engine quantity
fields are explicitly suffixed `_kg`; API input quantities are `_quintals`. Distances
accept metres of precision, expressed in km. Optimisation is bounded at 1000 quintals,
12 vehicle classes and 50 participants. Capacities model weight only; bulk/volume,
road restrictions and actual fleet availability must be checked by the coordinator.

The optimiser minimises total cost, then vehicle count, then unused capacity. Vehicle
code breaks remaining ties. It is an exact integer covering dynamic program, not a
greedy capacity heuristic. The same pure module can be imported by the net-realisation
engine without importing FastAPI or SQLAlchemy.

## Pooling contract

All lots in a pool share the same declared commodity, **one pickup point**, one destination
and one travel date. Joining explicitly means opting into those pool details. Grade,
variety, condition, farmer identity and quantity remain separately recorded. The coordinator
reviews physical compatibility; the backend does not infer it from historical prices.
Farm-to-pickup costs and multi-stop collection/routing are outside this first version.

- `POST /v1/pools`: coordinator creates a pool with a maximum quantity, not a reserved vehicle.
- `GET /v1/pools`: paginated open-pool discovery. `GET /v1/me/pools`: your history.
- `POST /v1/pools/{id}/join`: own lot only; creates a pending request.
- `POST /v1/pools/{id}/members/{member_id}/review`: owner coordinator approves/rejects.
- `POST /v1/pools/{id}/withdraw`: member leaves while open; a fresh join requests approval again.
- `POST /v1/pools/{id}/quote`: approved lots only; saved quote is returned after locking.
- `POST /v1/pools/{id}/transition`: OPEN → LOCKED → DISPATCHED → SETTLED.
  OPEN and LOCKED may also become CANCELLED. No other transitions are allowed.
- `GET /v1/pools/{id}/events`: coordinator-only audit history.

Review, withdrawal and transition requests include `expected_version` from the last
pool response. A stale version returns 409. Every membership mutation increments the
parent version; SQLAlchemy checks it atomically at commit to prevent approval/lock races.
Reload before retrying a 409. Quotes are not reservations; repeated quote calls have no
side effects. Duplicate active join requests are rejected rather than duplicated.

Locking requires all pending requests to be resolved and at least one approved lot.
It freezes the chosen vehicles, input provenance and exact cost allocation. Cost shares
are proportional to weight, with the largest-remainder method allocating leftover paise
deterministically by participant ID. Shares always sum to the total. Individual savings
are **solo cost minus allocated pooled cost**, not a proportional distribution of group
savings. Quotes expose negative individual savings; locking rejects them. This guard is
a proposed first-version policy for team review, not a claim from the source datasets.

Dispatch requires `transport_reference` (the coordinator's arrangement record). Settlement
requires an outcome `note`; it records trip completion, **not a payment or verified sale**.
Cancellation requires a note. There is no transporter marketplace, booking integration,
payment processor, price prediction, route optimiser, or produce quality verification.

## Data findings

See `../docs/TRANSPORT_DATA_REVIEW.md`. The snapshots contain price/arrival observations,
**not transport rates, road distances or coordinates**. `seed-markets` imports only exact
current-feed identities and sources. It deliberately does not merge CEDA names by fuzzy
matching. Import is repeatable and leaves existing catalogue records untouched.

No real quote is possible until a team member supplies an actual pickup point, sourced
road distance and transport rate card. No haversine fallback is implemented because
the existing datasets contain neither coordinates nor a justified road multiplier.
Routes and cards are append-only through the API: create a new version and use its ID
when inputs change. Existing pools retain their selected inputs and locked snapshot.

## PostgreSQL and integration

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@HOST:5432/mandiwise'
uv run alembic upgrade head
uv run uvicorn mandiwise_transport.api:create_app --factory --host 127.0.0.1 --port 8000
```

Schema uses `transport_` table prefixes to avoid claiming the project's entire database
design. The small `transport_users` table is a temporary identity integration boundary.
Replace `current_user` with the project's verified identity provider when that exists,
and migrate the foreign keys; never accept caller-supplied user IDs or role headers.
JWT validation currently uses fixed HS256, issuer `mandiwise`, audience `mandiwise-transport`,
expiry, issue time and subject checks. Production needs your normal user onboarding/token
delivery, HTTPS, secret management, database backups and an API gateway request limit.
No CORS origins are enabled by default; use a same-origin proxy or deliberately configure
the actual frontend origin at integration time. Run schema migrations explicitly before
starting the service; the server never creates tables implicitly.

## Verification

```powershell
uv run pytest -q
uv run ruff check src tests scripts migrations
uv run python scripts/study_data.py --data-dir ../data
```

Tests include comparison with exhaustive enumeration across 100 generated small fleets,
capacity boundaries, exact rounding/apportionment, authorisation, membership privacy,
stale input rejection, optimistic concurrency, complete lifecycle, migration/schema
agreement and idempotent import of the actual repository data. `TEST_POSTGRES_URL`
enables the optional PostgreSQL migration/concurrency test against an isolated temporary
schema. The ordinary suite always uses temporary SQLite databases, never the development DB.
