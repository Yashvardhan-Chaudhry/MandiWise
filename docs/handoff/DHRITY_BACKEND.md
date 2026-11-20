# Handoff: backend defect fixes (for Dhrity)

**Written 2026-11-19.** Every line reference, command result and number below was checked against
the code on `main` (commit `3eb7f7f`) on that date. If you start on a later commit, line numbers
will have moved, so search for the quoted code rather than trusting the number.

This brief is meant to be enough on its own: you shouldn't need to open another document to start.
Links to the deeper documents are in section 8.

---

## 1. What MandiWise is, and what's in `backend/`

MandiWise ranks mandis by **net realisation**: what a farmer actually keeps after commission,
market fee (cess), handling and transport. It is built on daily government price data
(AGMARKNET via data.gov.in, plus historical CEDA data). It also lets farmers **pool transport**:
several farmers share one vehicle, each farmer's lot stays separately bagged and sold under their
own name, and the transport cost is split in proportion to quantity. The pooling argument rests on
one fact. Transport is priced per vehicle, so cost per quintal is a step function and a small lot
pays for a lot of empty space. The premise is validated: median gross price spread across nearby
mandis is 73.1% over 2,821 same-day cross-sections. Net realisation is **not** yet proven, and
transport rates are still unsourced placeholders.

`backend/` is a FastAPI + SQLAlchemy service (SQLite locally, Postgres in CI). Package:
`backend/src/mandiwise_transport/`.

| File | What it is | Rule it must obey |
|---|---|---|
| `engine.py` | Pure arithmetic: `kg()`, `paise()`, `optimise()` (exact DP for the cheapest vehicle mix), `allocate_cost()` (largest-remainder split that conserves every paisa), `pool_quote()`. Integer kg and paise internally. | No DB, HTTP or framework imports. Values in, values out. |
| `db.py` | SQLAlchemy models: `User`, `PortalAccount`, `PortalMessage`, `Location`, `Route`, `RateCard`, `Pool`, `Member`, `PoolEvent`. `Pool` uses `version_id_col` for optimistic locking. | Must match the Alembic migrations exactly (a test checks this). |
| `schemas.py` | Pydantic request models (`extra="forbid"`, Decimal quantities and money). | Validation only. |
| `services.py` | Application rules: loads route and rate card, checks validity dates, builds the provenance block, enforces the pool lifecycle (`transition`), and builds the pool view. Delegates arithmetic to `engine.py`. | No arithmetic of its own (it currently has some, see "Ownership"). |
| `api.py` | `create_app()`, JWT/cookie auth (`current_user`), the `/v1/...` routes (catalogue, quotes, pools), and error mapping. Mounts the presentation and portal routers. | No business arithmetic in handlers. |
| `portal.py` | The farmer portal backend: password registration and login (scrypt, HttpOnly cookie), trip posting, discovery, workspace, and chat. Routes under `/portal/api/...`, page at `/pooling`. | Same as above. |
| `presentation.py` | The stateless classroom calculator `POST /demo/calculate`, the page at `/demo`, and the local launcher (`python -m mandiwise_transport.presentation`), which uses `portal.db` + `create_all`. | Same as above. |
| `cli.py` | Admin utilities: `create-user`, `token`, `seed-markets`. | |
| `web/templates/`, `web/static/` | Old server-rendered UI (`transport_demo.html`, `pooling.html`, `vehicles.js`, `pooling.js`, `calculator.js`). | Being replaced by Sarthak's React `frontend/`. |
| `migrations/` | Alembic: `0001_transport.py` (core tables), `0002_portal.py` (portal accounts and messages). | Every model change needs a new migration. |
| `tests/` | pytest: `test_engine.py`, `test_api.py`, `test_portal.py`, `test_presentation.py`, `test_http.py`, `test_migrations.py`, `test_postgres.py` (skipped unless `TEST_POSTGRES_URL` is set). Fixtures in `conftest.py`. | |

Outside `backend/`, your original module lives at `src/mandiwise/` (`models.py`, `recommendation.py`,
`transport.py`). Its tests are in `tests/test_recommendation.py` and `demo.py` runs it. The decision of
2026-09-17 made `backend/.../engine.py` canonical for vehicle packing and pool split, and made
`net_realisation` a **rebuild** in that engine. Your worked example becomes the rebuild's acceptance
test and your validation rules become its input spec. `src/mandiwise/` still runs `demo.py`, so its
defects (items 6 to 10 below) still count.

---

## 2. Setup and commands, with today's results (2026-11-19)

Windows, from the repo root `C:\Users\chaud\MandiWise`. `uv` (0.11.18) is installed and
`backend\.venv` already exists. CI runs Python 3.12 on `ubuntu-latest`. The local venv here is
Python 3.14.5, so if something passes locally but fails in CI, check the version first.

```powershell
# Backend: install, lint, test
cd backend
uv sync --frozen --extra test
uv run ruff check src tests scripts migrations
uv run pytest -q
# Offline fallback: .venv\Scripts\python.exe -m pytest -q

# Root (your recommendation engine) and the demo
cd ..
python -m unittest discover -s tests -v
python demo.py

# Local server (calculator at /demo, portal at /pooling). It creates backend\portal.db.
cd backend
.venv\Scripts\python.exe -m mandiwise_transport.presentation --port 8001 --no-browser
# To keep your real portal.db untouched, first run:  $env:PORTAL_DATABASE_URL = 'sqlite:///C:/temp/scratch.db'

# Full API with Alembic instead of create_all (see backend/README.md):
$env:JWT_SECRET = uv run python -c "import secrets; print(secrets.token_urlsafe(48))"
$env:DATABASE_URL = 'sqlite:///./transport.db'
uv run alembic upgrade head
uv run uvicorn mandiwise_transport.api:create_app --factory --host 127.0.0.1 --port 8000
```

**What I observed on 2026-11-19, on the pre-merge `main`.** On today's `main` the backend suite is **78 passed, 1 skipped** (PR #1 added the net-realisation and ranking tests), the root suite is 5, and the frontend suite is 7.

| Check | Result |
|---|---|
| `uv run ruff check src tests scripts migrations` | `All checks passed!` |
| `uv run pytest -q` | **50 passed, 1 skipped** (Postgres test, no `TEST_POSTGRES_URL`), 2 deprecation warnings from starlette/httpx, 37.7 s |
| `python -m unittest discover -s tests -v` | **5 tests, all OK** |
| `python demo.py` | Prints the PLACEHOLDER rate-card warning first, then Mandi B (distant) ₹48,592.00 net and Mandi A (local) ₹42,480.00 net, each with 2 × Tempo |
| Server smoke test (port 8011) | `GET /health` → 200 `{"status":"ok"}`; `GET /demo` → 200 HTML; `POST /demo/calculate` (2 farmers, canonical card, 50 km) → 200 with **no auth**, ₹3,500 truck split ₹1,400 / ₹2,100; `GET /portal/api/trips` → 200 `[]` with no auth |
| Worst-case `/demo/calculate` (1000 q, 12 vehicle types, 8 farmers) | **3.46 s of server CPU per request**, measured 3 times, unauthenticated |
| Same pytest suite with India's date one day ahead of the machine's | **8 failed, 42 passed**. See new defect N1. |

So everything is green today, but the suite has a time-of-day failure (N1) that CI can hit.

---

## 3. Working rules (restated in full: these are what reviewers check)

1. **The engine is pure.** `engine.py` (and `src/mandiwise/`) has no database, HTTP or framework
   imports and no I/O. Values in, values out. That is what makes it testable against hand-computed numbers.
2. **No business arithmetic in route handlers or in the client.** If a calculation lives in
   `api.py`, `portal.py`, `presentation.py` or in JavaScript, it has escaped the test suite. Put it in the
   engine and call it.
3. **Rates are data, not code.** Commission, cess, handling and vehicle rates live in database tables,
   each with a **source** and an **effective date**.
4. **Never fabricate a number.** If a rate, price or distance isn't sourced, it is a **placeholder**
   and is labelled as one everywhere it appears, including after it has been saved.
5. **Every price carries its reporting date.** Stale data is shown greyed out, never hidden and never
   silently substituted.
6. **The external API is never called in the request path.** Ingestion runs on a schedule only.
7. **`docs/DECISIONS.md` is append-only.** Never edit or delete an entry. To change a decision, append a
   new dated entry that says which entry it supersedes and why.
8. **Commit under your own GitHub account.** Git history is contribution evidence. Don't reuse
   anyone else's email, and don't add co-authors you didn't work with.
9. **Feature branch plus PR to `main`.** `main` is protected: a PR and 1 approval are required, and force
   pushes are blocked. Don't merge or force-push someone else's work.
10. **Never commit `.env`, databases (`*.db`, including `backend/portal.db`), credentials, venvs or
    caches.** `.gitignore` already covers `*.db` and `.env`. Check `git status` before you commit anyway.
11. **Keep migrations consistent with the models.** Any change to `db.py` needs a new Alembic revision
    in `backend/migrations/versions/` (next is `0003_...`, `down_revision = "0002"`).
    `tests/test_migrations.py` fails if the models and migrations disagree.
12. **Every fix needs a test.** It should fail before your change and pass after it.

---

## 4. Ownership boundaries: read before branching

**Not yours (Yashvardhan; merged into `main` in PR #1):**
- Rebuilding `net_realisation` inside `backend/src/mandiwise_transport/engine.py`, adding market fee and the min/max range.
- Moving the trip-cost formula (`base + per_km × distance`) out of `services.py:49-53` and
  `presentation.py:66` into `engine.py`. TASKS.md lists this as "Move the trip-cost formula into
  the engine". That task is **his**, not yours.
- A new `rankings.py` router: `GET /v1/markets`, `GET /v1/commodities`, `POST /v1/rankings`.
- The DECISIONS.md entry for the **staleness threshold** used by the API (see item 10).

**Status (2026-11-20): all four are done and merged into `main`** (PR #1). The React client
(PR #4) and the report (PR #5) are merged too, and `main` is now the only branch. Start from it:

```
git fetch origin
git switch main && git pull
git switch -c fix/backend-defects
```

What changed in those files (so your line numbers stay right):
- `engine.py`: new `trip_cost_paise`, `net_realisation`, `rank_offers`. `pool_quote` now also
  returns `individual_total_inr` and each member's `individual_vehicles`.
- `services.py` / `presentation.py`: call `trip_cost_paise`. `presentation.py` no longer sums the
  solo totals or re-runs the optimiser per farmer, so item 4's cost is now one optimiser run per
  farmer inside `pool_quote` plus one for the pool.
- `api.py`: `create_app(..., data_dir=None)`, and the new `rankings` router is included.
- New: `pricing.py`, `rankings.py`, `tests/test_net_realisation.py`, `tests/test_rankings.py`,
  `data/market_rates.json`. Backend suite is now 78 passed, 1 skipped.
- The staleness decision (item 10) is in DECISIONS.md, 2026-11-19: a price is stale when it is
  **more than 2 days** old. That is exactly what `recommendation.py:25` already does, so item 10
  becomes: reference that entry from the code and rename the parameter if you want the name to say
  "more than". The `src/mandiwise/` items (6 to 9) touch none of those files. If you want to start
them before his merge, put them on their own branch and confirm with him first.

The TASKS.md item "Carry reported min and max prices through to a net realisation range" is
coupled to his rebuild. Don't start it without asking him.

**Not yours (Sarthak):** the new React client in `frontend/`. Don't edit the old
`web/templates/*.html` / `web/static/*.js` unless a backend fix needs it (for example, item 2 changes
what the trip-posting API accepts). If it does, keep the template change minimal and tell Sarthak
what the API contract now is.

**Yours:** the backend defects in section 5, the `src/mandiwise/` defects, and their tests.

---

## 5. Prioritised defect list

Severity: **High** means it breaks a core working rule or makes a user-visible flow impossible.
**Medium** means it's wrong but has a workaround or a narrow trigger. **Low** is cleanup. Items
marked **NEW** were found on 2026-11-19 and are not in TASKS.md yet. Add them when you claim them.

### Summary table

| # | Title | Severity | Needs migration | Needs DECISIONS entry |
|---|---|---|---|---|
| N1 | **NEW** Test fixtures use machine date, server uses IST: 8 tests fail in CI evenings | High (blocks PRs) | No | No |
| 2 | Invented rates persist as real (`is_demo=False`) | High | Probably (new flag/column) | Yes |
| 3 | Stuck pool: no way to reach LOCKED or remove a member | High | Maybe (member status) | Yes |
| 1 | Pool Coordinator is a role, not a permission | High | **Yes** | **Yes** |
| 4 | `POST /demo/calculate` unauthenticated and unthrottled, about 3.5 s CPU per call | High | No | Short one advised |
| N2 | **NEW** Rejected farmer can re-request at once and keep the pool un-lockable | Medium | No | Yes (is rejection final?) |
| 5 | Rate provenance dropped from portal summary responses | Medium | No | No |
| 11 | `join` takes no `expected_version` | Medium | No | No |
| N3 | **NEW** Portal trip posting writes into the shared admin catalogue | Medium | No | Advised |
| 6 | `src/mandiwise` reads the wall clock; tests don't pass `today=` | Medium | n/a | No |
| 7 | Breakdown components don't sum to the displayed net | Medium | n/a | No |
| 9 | Root tests use the superseded base-0 rate card | Medium | n/a | No |
| 8 | No multi-vehicle test in `tests/test_recommendation.py` | Medium | n/a | No |
| 10 | Staleness threshold undocumented, off-by-one in name | Medium | n/a | Yashvardhan writes it |
| N4 | **NEW** 50-member cap counts rejected and withdrawn rows | Low | No | No |
| N5 | **NEW** Global throttle table can lock out everyone | Low | No | No |
| N6 | **NEW** `distance_km` returned as a float in portal summary | Low | No | No |
| N7 | **NEW** `DEMO_BRIEF.md` overclaims a DB constraint on lifecycle transitions | Low (doc) | No | No |

---

### N1. NEW: test fixtures use the machine's date, the server uses India's date

- **Severity:** High. It will fail your own PRs on CI at certain hours.
- **Where:** `backend/tests/conftest.py:42` (`today = date.today()`, then used as `travel_date` at
  `:102` and route/card validity at `:67-68`); `backend/tests/test_api.py:79`. The server side uses
  `services.today()` at `backend/src/mandiwise_transport/services.py:13-15`, which is
  `datetime.now(ZoneInfo("Asia/Kolkata")).date()`.
- **What's wrong:** CI runs on `ubuntu-latest`, which uses UTC. From 18:30 to 23:59 UTC
  (00:00 to 05:29 IST) the IST date is one day ahead, so the fixture's `travel_date` is "yesterday"
  to the server and `create_pool` returns 422 `past_trip` (`api.py:231`). I reproduced it by making
  `svc.today()` return the machine date plus 1: **8 failed, 42 passed**
  (`test_complete_pool_lifecycle`, `test_privacy_and_ownership`,
  `test_capacity_duplicates_pending_and_stale_version`,
  `test_optimistic_concurrency_prevents_lost_updates`, `test_withdrawal_and_cancellation`,
  `test_withdraw_and_rejoin_requires_new_approval`, `test_other_member_share_is_not_visible_after_lock`,
  `test_lock_refuses_individual_cost_increase`). `test_portal.py` and `test_postgres.py` already
  import `services.today` correctly. Only `conftest.py` and `test_api.py` are inconsistent.
- **Why it matters:** a flaky suite costs reviewers time and hides real failures. "Deterministic" is a
  stated engine principle.
- **Done when:** fixtures and tests derive dates from `mandiwise_transport.services.today()`, or the
  clock is pinned with `monkeypatch` so the suite is date-independent, and the simulation above
  passes.
- **Approach:** in `conftest.py` replace `date.today()` with `from mandiwise_transport.services import today`.
  Do the same at `test_api.py:79`. Better still, add a fixture that monkeypatches `svc.today` to a fixed
  date, so tests don't depend on the clock at all.
- **Tests:** a test that monkeypatches `services.today` to `date.today() + 1 day` and runs the
  pool-creation path. Do this one **first**. It's small and it protects every later PR.

### 2. Invented rates persist as if they were real

- **Severity:** High. This is the "never fabricate a number" rule failing.
- **Where (verified):**
  - `web/static/vehicles.js:13-14` pre-fills every vehicle editor with `Tempo 30 q / ₹1000 / ₹10/km`
    and `Truck 100 q / ₹2500 / ₹20/km`. These are the repo's **placeholder** card
    (`data/vehicle_rates.json`, DECISIONS 2026-09-17, "UNSOURCED placeholders"), but in the portal
    nothing labels them as placeholders.
  - `web/static/pooling.js:125` attaches that editor to the **real, persisted** trip-posting form.
    `pooling.js:546-570` submits it.
  - `portal.py:238-307` (`post_trip`) saves the card with `is_demo=False` (`portal.py:271`) and
    `source = "Organizer-entered transport estimate; unverified supplier rates and distance"` (`portal.py:242`).
  - `services.py:76-79` adds the "Synthetic demonstration rates; not a real transport quotation."
    warning **only** when `is_demo` is true, so a portal trip's quote carries no such warning.
  - The "rates-confirmed" checkbox (`templates/pooling.html:179-187`) is `required` in the browser,
    but `pooling.js:551-563` never sends it, `portal.Trip` (`portal.py:148-169`) has no field for it,
    and the API accepts a post without it.
- **Failure scenario (reproduced):** a farmer posts a trip and leaves the pre-filled numbers alone.
  `GET /v1/rate-cards` then shows `is_demo: false`, and `POST /v1/pools/{id}/quote` returns
  `"is_demo": false` with only the 3 generic warnings and no synthetic-rates warning. The placeholder
  ₹1000/₹10 now looks like an organiser's real quote to every member and every downstream
  consumer of `/v1`.
- **Why it matters:** working rule 4 (a placeholder must stay labelled) and rule 3 (rates carry a
  real source).
- **Done when:** there is no path by which an unsourced number reaches a saved trip classified as
  sourced. Concretely: the server decides the classification, not the client. A user-entered card is
  stored with an explicit "unverified / organiser-entered" status that `services.inputs` turns into a
  visible warning. Any value that equals an untouched placeholder default can't be saved as
  confirmed. If you keep a "rates confirmed" attestation, the API requires it and stores it.
- **Suggested approach:** don't overload `is_demo` (it means synthetic demo data). Add a column such
  as `RateCard.provenance` with values like `sourced` / `organiser_entered` / `demo`, or a boolean
  `verified`, and have `services.inputs` emit a warning for anything that isn't `sourced`.
  Add `rates_confirmed: Literal[True]` to `Trip`. Remove the numeric defaults from the portal editor,
  or render them as visibly-labelled placeholders that the user must overwrite. That last part is a
  `web/static` edit, so tell Sarthak so `frontend/` does the same.
- **Tests:** posting a trip produces a quote whose `warnings` mention unverified rates; a post without
  `rates_confirmed` is rejected with 422; the migration test still passes.
- **Migration:** yes, if you add a column (`0003_...`). **DECISIONS:** yes. Record how
  organiser-entered rates are classified and displayed.

### 3. Stuck pool: a coordinator can't reach LOCKED or remove a member

- **Severity:** High. Normal use can make a pool permanently un-lockable.
- **Where:** `services.py:146-155` (lock refuses if any approved participant's share exceeds their
  solo cost: `member_cost_increase`, `:151-154`); `api.py:331-332` (`review` refuses any member who is
  not PENDING: `already_reviewed`). There is **no remove-member endpoint**. The member routes are
  `join`, `review` and `withdraw` only.
- **Failure scenario (reproduced today, canonical placeholder card, 50 km):** the organiser posts a
  trip with their own 30 q lot (solo cost 1 Tempo = ₹1,500). Farmer B joins with 5 q (solo cost ₹1,500)
  and is approved. Together 35 q needs 2 Tempos = ₹3,000, split by quantity: B pays ₹428.57 and the
  organiser pays **₹2,571.43, more than travelling alone**. Lock → 409 `member_cost_increase`.
  Trying to reject B → 409 `already_reviewed`. The only exits are B voluntarily withdrawing, the
  organiser withdrawing their own lot, or cancelling the trip. The step-function cost structure
  makes this reachable in normal use, not just in edge cases.
- **Why it matters:** ARCHITECTURE §6 gives the coordinator a rejection right and requires the
  lifecycle to always be completable (OPEN → LOCKED or CANCELLED). Here the coordinator loses the
  ability to act on a member once they've approved them.
- **Done when:** from any OPEN state, the coordinator can always reach LOCKED or a clean
  cancellation without needing another member to cooperate. Every such action is recorded as a
  `PoolEvent`.
- **Suggested approach (pick one, and record it):**
  (a) a `POST /v1/pools/{id}/members/{member_id}/remove` (coordinator only, OPEN only,
  `expected_version`), setting a new status `REMOVED`, or reusing `REJECTED`, with a mandatory note; or
  (b) allow re-reviewing an APPROVED member back to REJECTED while OPEN; and/or
  (c) let the coordinator lock with an explicit, recorded acknowledgement that a named member pays
  more, provided that member has consented. Option (a) is the simplest to reason about. Whatever
  you choose, make the lock error say **which** participant is worse off, so the UI can tell the
  coordinator what to do. Today it doesn't.
- **Tests:** the exact 30 q + 5 q scenario above, ending in a successful lock after removal; a
  non-coordinator can't remove; removal outside OPEN is refused; a stale version is refused.
  Note that `test_api.py::test_lock_refuses_individual_cost_increase` pins the current refusal. Keep it,
  and extend it to show the remedy.
- **Migration:** yes, if you add `REMOVED` to the member status CHECK (`db.py:138` and
  `migrations/versions/0001_transport.py:99`; change it in a new `0003` revision, don't edit `0001`).
  **DECISIONS:** yes. Record the remedy policy.

### 1. Pool Coordinator is modelled as a role, not a permission

- **Severity:** High. The code contradicts a recorded decision.
- **Decision being contradicted:** DECISIONS 2026-08-20, "Pool Coordinator is a permission on a farmer
  account, not a separate user type."
- **Where:**
  - `db.py:40`: `CheckConstraint("role IN ('farmer','coordinator','admin')")`. The roles are mutually
    exclusive. The same CHECK is in `migrations/versions/0001_transport.py:19`.
  - `api.py:229-230`: `POST /v1/pools` requires `user.role == "coordinator"`, so a `farmer` (and an
    `admin`) **cannot create a pool**.
  - `portal.py:113`: every portal self-registration is created with `role="coordinator"`. Confirmed:
    `GET /v1/me` for a fresh portal user returns `"role": "coordinator"`. This makes `farmer` dead in
    the portal.
  - `portal.py:240`: `post_trip` allows `{"farmer", "coordinator"}`, a **different rule** from
    `api.py:229` for the same action (creating a pool).
  - `cli.py:76` offers all three roles.
- **Failure scenario:** a farmer created via `mandiwise-transport create-user --role farmer` calls
  `POST /v1/pools` → 403 "Pool coordinator permission required", but the same farmer could open a pool
  through `/portal/api/trips`. Two doors to one action, with two different locks.
- **Done when:** one authorisation rule for "create a pool", used by both `/v1/pools` and the portal;
  a farmer can open a pool; the schema matches whichever decision stands.
- **Suggested approach:** either (a) implement the decision: roles become `farmer` / `admin`, and
  "coordinator" becomes either a boolean `can_coordinate` on the user or (simplest) the fact of being
  `Pool.coordinator_id` for that pool. Data migration: existing `coordinator` rows become `farmer`.
  Or (b) append a **new dated DECISIONS entry** that supersedes the 2026-08-20 one, saying why roles
  stayed separate. Then fix only the inconsistency between `api.py:229` and `portal.py:240`. Put the
  rule in one function in `services.py` and call it from both handlers.
- **Tests:** a farmer can create a pool via `/v1`; the portal and `/v1` give the same answer for the
  same user; an admin can't escalate through the portal (the existing
  `test_portal.py::test_password_auth_csrf_validation_and_no_admin_escalation` must still pass); the
  migration test passes. Several fixtures in `conftest.py` create `coordinator` users, so update them.
- **Migration:** **yes** (new revision changing the CHECK, plus a data migration for existing rows).
  **DECISIONS:** **yes**, either implementing or superseding the 2026-08-20 entry.

### 4. `POST /demo/calculate` is unauthenticated and unthrottled

- **Severity:** High for any deployment. It's an easy CPU denial of service.
- **Where:** route `presentation.py:59-90`; mounted on the **main** app for every deployment at
  `api.py:115` (`app.include_router(presentation_router)`). No auth dependency and no `throttle()`.
- **What's wrong (measured):** a single request with 1000 q, 12 vehicle types and 8 farmers took
  **3.46 s** of server CPU, every time, without credentials. The DP in `engine.optimise` is
  O(quantity_kg × vehicles), which is up to 100,000 × 12. The handler runs it once for the pool
  (`pool_quote`, which also calls it again for every participant at `engine.py:122`) and then
  **recomputes every farmer's solo plan a second time** at `presentation.py:72`. So TASKS.md's
  "roughly 1.2 million operations" understates it: one request does several full DP passes.
  `test_presentation.py::test_existing_api_has_demo_without_changing_auth` (lines 76-79) currently
  **asserts** that the endpoint answers 200 without auth on the main app, so that test pins the defect.
- **Done when:** the endpoint is either mounted only by the local demo launcher
  (`create_demo_app`, `presentation.py:93-106`) or authenticated and rate-limited on the main app.
  Remove the duplicate solo computation as well.
- **Approach:** move `app.include_router(presentation_router)` out of `create_app()` and into
  `create_demo_app()`, or add a flag. Reuse `portal.throttle(request, "calculate", N)` if it must
  stay public. Update the pinning test to assert the new behaviour. Careful: `presentation.py` and
  `api.py` are both touched by Yashvardhan's branch, so do this **after** his merge.
- **Tests:** on `create_app()` (without the demo launcher), `/demo/calculate` returns 401/404; on
  `create_demo_app()` it still works; if throttled, the (N+1)th call within a minute returns 429.
- **DECISIONS:** a short entry recording that the calculator is demo-only (or rate-limited) is advised.

### N2. NEW: a rejected farmer can re-request immediately and block the lock

- **Severity:** Medium.
- **Where:** `api.py:305-314`. `join` only refuses when the existing row is PENDING or APPROVED, so
  a `REJECTED` row is reused (`existing or Member(...)`, `:311`) and set back to `PENDING` (`:314`).
  `services.py:148-149` refuses to lock while any member is PENDING. `/v1/.../join` has no throttle.
- **Failure scenario (reproduced):** the coordinator rejects farmer C. C immediately calls `join`
  again → 201, PENDING. The coordinator tries to lock → 409 `pending_members`. C can repeat this
  indefinitely, so the coordinator's rejection right (ARCHITECTURE §6, safeguard 2) is not final.
- **Done when:** a rejection sticks for that pool (for example, `join` refuses when the existing
  status is `REJECTED`), or re-requests are limited and recorded. Either way, the behaviour is decided
  and tested.
- **Tests:** reject, then re-join returns 409; lock succeeds afterwards.
- **DECISIONS:** yes, a one-liner on whether rejection is final per pool.

### 5. Rate provenance dropped from portal summary responses (backend half)

- **Severity:** Medium.
- **Where:** `portal.py:172-195` (`summary`). It returns `"vehicles": card.vehicles` (`:193`) and a
  hard-coded `"rates_notice"` string (`:194`), but **not** `card.source`, `card.effective_from`,
  `card.effective_until`, `card.is_demo` (or the new provenance status from item 2), or `route.source`.
  `summary` is the payload behind `GET /portal/api/trips`, `GET /portal/api/trips/{id}`,
  `GET /portal/api/mine` and the `POST /portal/api/trips` response. By contrast, `/v1/...` quotes do
  carry `rate_source`, `rate_effective_from/until`, `distance_source` and `is_demo`
  (`services.py:56-75`).
- **Why it matters:** rule 5 ("every price carries its reporting date") and rule 3 (rates traceable to
  a source).
- **Done when:** every portal response that shows a rate also carries its source, effective dates and
  provenance status (the same field names as the `/v1` provenance block). The **client** half
  (`pooling.js:379-441` rendering them) is Sarthak's, so tell him the new fields.
- **Tests:** a posted trip's summary includes `rate_source`, `rate_effective_from`,
  `rate_effective_until` and the demo/unverified flag.

### 11. `join` doesn't take `expected_version`

- **Severity:** Medium (API contract consistency).
- **Where:** `api.py:297-321`. `join` uses `JoinInput` (`schemas.py:112-116`), which has no version
  field. `review` (`:327`), `withdraw` (`:348`) and `transition` (`services.py:134`) all call
  `svc.version(pool, body.expected_version)`.
- **What's wrong:** it isn't a lost-update race, because `Pool.version` is a SQLAlchemy
  `version_id_col` (`db.py:118`) and `svc.touch` bumps it, so concurrent commits raise
  `StaleDataError` → 409 (`api.py:80-84`). The gap is that a farmer can't say "I'm requesting to join
  the pool as I last saw it". Their request goes through even if the pool's approved load or
  membership changed under them. It also makes `join` the only mutating pool endpoint that clients
  call differently.
- **Done when:** `join` accepts `expected_version` (required, or optional with a dated deprecation
  if Sarthak's client needs time) and returns 409 `version_conflict` on mismatch.
- **Tests:** a join with a stale version → 409; with the current version → 201. Update
  `conftest.join()` and `test_portal.py` callers.

### N3. NEW: portal trip posting writes into the shared admin catalogue

- **Severity:** Medium.
- **Where:** `portal.py:243-259`. `post_trip` looks up a `Location` by name, kind, state and district,
  and **creates** one if it's missing, including `kind="mandi"`, with the organiser-entered source
  string. Creating `/v1/locations` is admin-only (`api.py:149-154`), but these rows land in the same
  `transport_locations` table. They are listed to every authenticated user by `GET /v1/locations`,
  and future trips reuse them by name. The same goes for the route and rate card (`portal.py:260-275`),
  which appear in `GET /v1/routes` and `GET /v1/rate-cards` and can be used by any coordinator in
  `POST /v1/pools`.
- **Failure scenario (reproduced):** after one portal post, a different farmer's `GET /v1/locations`
  returns `[("Probe Mandi", "mandi"), ("Village X", "origin")]`. A typo'd mandi name becomes a
  catalogue "mandi". `docs/transport/DEVELOPMENT.md` claims registration "never permits administrative
  catalogue writes", and that isn't true.
- **Done when:** user-entered locations are either kept separate from the curated catalogue (for
  example a flag or provenance column, filtered out of `/v1/locations` by default) or must match an
  existing catalogue mandi. The DEVELOPMENT.md sentence is corrected.
- **Tests:** after a portal post, `GET /v1/locations` (default) doesn't list the user-entered mandi.

### 6. `src/mandiwise` reads the wall clock

- **Severity:** Medium.
- **Where:** `src/mandiwise/recommendation.py:37` (`reference_day = today or date.today()`), in a
  module whose docstring says it "performs no I/O". In `tests/test_recommendation.py`, 3 of the
  5 tests don't pass `today=`: `test_project_worked_example_matches_exact_amounts` (`:30-31`),
  `test_mandis_are_ordered_by_net_not_headline_price` (`:38-42`) and
  `test_invalid_quantity_is_rejected` (`:47`).
- **Done when:** `today` is a required keyword argument (no `date.today()` anywhere in
  `src/mandiwise/`), every test passes it, and `demo.py` (which already passes
  `today=date(2026, 9, 17)` at line 53) still works.
- **Tests:** calling without `today` raises `TypeError`; staleness assertions use explicit dates.

### 7. Breakdown components don't sum to the net

- **Severity:** Medium (a farmer checking by hand gets a different answer).
- **Where:** `src/mandiwise/recommendation.py:43-49`. Each component is rounded with `money()`, but
  `net_realisation_inr` is `money(gross − commission − handling − transport)` on the **unrounded** values.
- **Failure scenario (reproduced, canonical Tempo card):** price ₹1,234.57, 33.333 q, commission 0.025,
  handling ₹12.345/q, 17.5 km gives gross 41,151.92 − commission 1,028.80 − handling 411.50 − transport
  2,350.00 = **37,361.62**, but the net shown is **37,361.63**.
- **Done when:** net is computed from the rounded components, so the displayed parts always sum
  exactly to the displayed total. Coordinate the rounding policy with Yashvardhan so the rebuilt
  engine matches (his engine works in integer paise).
- **Tests:** the case above, asserting `gross − commission − handling − transport == net`.

### 8. No multi-vehicle test in `tests/test_recommendation.py`

- **Severity:** Medium.
- **Where:** `tests/test_recommendation.py:16` defines `TRUCK` and never uses it. Every test runs a
  Tempo-only fleet. `demo.py:52` also filters the card to Tempo only.
- **Done when:** a test that a naive `ceil(quantity / capacity)` implementation would fail, plus a
  capacity-boundary case. With the canonical card at 50 km (both checked today): 70 q → 1 × Truck
  ₹3,500 (not 3 × Tempo ₹4,500); 100 q → 1 × Truck ₹3,500; **101 q → 1 × Tempo + 1 × Truck ₹5,000**
  (one quintal over the truck's capacity).

### 9. Root tests use the superseded base-0 rate card

- **Severity:** Medium (it contradicts the one-card decision).
- **Where:** `tests/test_recommendation.py:15-16`. `TEMPO = 30 q, base ₹0, ₹75/km` and
  `TRUCK = 100 q, base ₹0, ₹100/km`. DECISIONS 2026-09-17 ("One rate card") replaced the base-0 card
  with `data/vehicle_rates.json` (Tempo 30 q / ₹1,000 + ₹10/km; Truck 100 q / ₹2,500 + ₹20/km),
  because base 0 hides the fixed cost that the whole pooling argument relies on.
- **Catch (verified today):** you can't just swap the card in. Under the canonical card,
  `test_mandis_are_ordered_by_net_not_headline_price` **flips**: "Far but expensive" nets ₹48,560.00
  against "Local" ₹42,480.00, so the assertion that Local wins fails. The worked example becomes A
  ₹42,480.00 and B ₹48,592.00 (not ₹41,880 / ₹42,792), and the tie-break test's prices were tuned to
  ₹75/km, so they no longer tie.
- **Done when:** either the tests load the canonical card from `data/vehicle_rates.json`, with new
  hand-computed inputs and expected values that preserve each test's intent; or the base-0 card is kept
  only as an explicitly named fixture (for example `SYNTHETIC_BASE0_TEMPO`) with a comment saying it is
  not the project card and why the test needs it. The worked example is your hand-verified acceptance
  case for Yashvardhan's rebuild, so agree the numbers with him.

### 10. Staleness threshold undocumented

- **Severity:** Medium.
- **Where:** `src/mandiwise/recommendation.py:25` (`stale_after_days: int = 2`) and the comparison at
  `:42` (`reported_on < reference_day - timedelta(days=stale_after_days)`). Checked today: with today
  2026-09-17, a price reported on 09-15 is **not** stale and one reported on 09-14 **is**. So "stale
  after 2 days" actually means stale at 3 or more days old.
- **Ownership:** **Yashvardhan will record the threshold decision in DECISIONS.md** for the API.
  Don't write a competing one. Once his entry exists, make `src/mandiwise` match it: same number,
  same inclusive/exclusive meaning, and a parameter name that says which.
- **Tests:** boundary tests at exactly the threshold and one day either side.

### N4. NEW: 50-member cap counts rejected and withdrawn rows

- **Severity:** Low. **Where:** `api.py:307`, where `len(rows) >= 50` counts every member row in any
  status. After 50 distinct people have ever requested, newcomers are refused even if most were
  rejected. **Fix:** count only PENDING and APPROVED. **Test:** 50 rejected rows plus a new joiner succeeds.

### N5. NEW: global throttle table can lock out every user

- **Severity:** Low (prototype). **Where:** `portal.py:55`. When the in-process `_attempts` dict
  holds more than 10,000 keys (one per category and IP within 60 s), **every** auth, create and chat
  request from anyone gets 429. **Fix:** evict the oldest entry instead of refusing everyone, or reject
  only new keys. `docs/transport/DEVELOPMENT.md` already says a shared store is needed before deployment.

### N6. NEW: `distance_km` is a float in portal summaries

- **Severity:** Low. **Where:** `portal.py:189`, `route.distance_m / 1000`. Everywhere else, money and
  distance are Decimal strings (`services.py:61`). **Fix:** `str(Decimal(route.distance_m) / 1000)`.

### N7. NEW (doc): `DEMO_BRIEF.md` overclaims a database constraint

- **Already fixed** in the docs PR (Yashvardhan, 2026-11-19); kept here for the record.
- **Where:** `docs/DEMO_BRIEF.md:63` said invalid transitions are rejected "with a database constraint
  behind that as well". The only constraint is `CheckConstraint("state IN (...)")` (`db.py:121`,
  `0001_transport.py:85`). It restricts **values**, not **transitions**. OPEN → SETTLED is blocked
  only by the Python table at `services.py:135-141`. Either soften the sentence (tell Yashvardhan,
  who owns the demo docs) or, if you want a real guarantee, add a DB trigger. That's probably not worth it.

---

## 6. Suggested order of work

1. **Now, no conflict risk:** read this brief, run section 2's commands, claim your items in
   `docs/TASKS.md` (put your name next to them and add the NEW items).
2. **Small, self-contained first PR:** items 6, 7, 8 and 9 in
   `src/mandiwise/` and `tests/test_recommendation.py`. Agree the worked-example numbers (item 9) with him.
3. **On a branch from fresh `main`:**
   a. N1 (test clock): small, and it protects every later PR.
   b. Item 1 (coordinator permission): migration plus DECISIONS. Do it before 2 and 3 because it
      changes who can do what, and their tests depend on that.
   c. Item 2 (invented rates) together with item 5 (provenance in summaries): same files, same
      migration if you add a provenance column.
   d. Item 3 (stuck pool) together with N2 (rejection finality) and item 11 (`join` version): all
      membership lifecycle.
   e. Item 4 (demo endpoint).
   f. N3, then N4, N5, N6.
   g. Item 10 once Yashvardhan's staleness entry is in DECISIONS.md.
4. Several small PRs are easier to review than one large one. Grouping by the letters above works well.

### Definition of done for each PR

- [ ] `uv run ruff check src tests scripts migrations` → `All checks passed!`
- [ ] `uv run pytest -q` green, including your **new** tests (each one failed before the fix)
- [ ] `python -m unittest discover -s tests -v` green, and `python demo.py` still runs and prints the placeholder warning
- [ ] Any `db.py` change has a new Alembic revision; `tests/test_migrations.py` passes (it upgrades,
      compares models to the schema, and downgrades)
- [ ] `docs/TASKS.md` checkboxes ticked with `claimed by: Dhrity` and a dated "done" note
- [ ] New dated entries **appended** to `docs/DECISIONS.md` where marked above. Nothing edited or deleted.
- [ ] No `.env`, `*.db` (including `backend/portal.db`) or credentials in `git status`
- [ ] Commits under your own GitHub account; PR to `main` describing scope, setup, tests and known
      limits; 1 approval
- [ ] If an API response shape changed, Sarthak has been told the new fields for `frontend/`

---

## 7. Who to ask

- **Yashvardhan**: data pipeline, the canonical engine and the `net_realisation` rebuild, the new
  rankings API, the staleness decision, demo docs (`DEMO_BRIEF.md`, `DEMO_RUNBOOK.md`), CI.
- **Sarthak**: wrote `backend/` originally (portal, lifecycle, calculator, migrations). Ask him about
  original intent before changing behaviour. He owns the new `frontend/`, so tell him about any API
  contract change.
- If a fix needs something not yet decided, check `docs/DECISIONS.md` first, then ask the group
  **before** coding. Don't guess.

## 8. Where the depth lives

| Topic | File |
|---|---|
| Project state, open risks, working rules | `claude.md` (repo root, local) |
| Architecture: layers, engine formula (§3.3), pool lifecycle (§6) | [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) |
| Every decision and why (append-only) | [`docs/DECISIONS.md`](../DECISIONS.md) |
| All tasks, including the 2026-09-17 audit write-ups | [`docs/TASKS.md`](../TASKS.md) |
| Backend setup, API walkthrough, Postgres | [`backend/README.md`](../../backend/README.md) |
| Portal auth, data and deployment limits | [`docs/transport/DEVELOPMENT.md`](../transport/DEVELOPMENT.md) |
| Branch, PR and commit rules | [`CONTRIBUTING.md`](../../CONTRIBUTING.md) |
| Placeholder rate card | [`data/vehicle_rates.json`](../../data/vehicle_rates.json) |
| CI definition | `.github/workflows/transport.yml` |
| Data findings (73.1% spread) | `research/findings.md` |
