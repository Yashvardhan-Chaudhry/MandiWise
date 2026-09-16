# Tasks

Not role-based. We're three beginners building this together, so work is broken into concrete tasks instead of fixed ownership per person. Anyone can pick up any task. Claim a task by putting your name next to it before you start, so two people don't duplicate work.

Build order follows claude.md's "Next steps": schema → engine → API → client. Don't start a later stage's tasks until the stage before it has something working — the engine can't be tested without a schema to pull rate/distance data from, the API can't be tested without an engine, etc.

Format: `[ ] Task — claimed by: — what "done" looks like`

## Contribution under review — Sarthak / transport

Sarthak Kaushik (`@TheSarthak08`) has prepared the transport backend, exact vehicle
selection/cost split, saved pool lifecycle, calculator and farmer-connection prototype
on `sarthak/transport-pooling-portal`. See
[`transport/CONTRIBUTION.md`](transport/CONTRIBUTION.md) for scope, setup and review checks.
The existing stage checkboxes below are intentionally unchanged: branch implementation
is not the same as team-reviewed integration or completion of the broader project tasks.

---

## Stage 0 — before any code

- [ ] Idea pitch to professor — claimed by: — professor has approved the idea, or given specific change requests to act on
- [ ] Placeholder deployed to a live URL (per claude.md step 2 — do this before features exist) — claimed by: — a URL exists and loads something, even a static "MandiWise — coming soon" page
- [ ] Data validation pull run (see `research/findings.md` for the two measurements) — claimed by: — `research/findings.md` has real numbers in its Results sections, not placeholders

## Stage 1 — schema

Reference: `docs/ARCHITECTURE.md` §5 (Core entities)

- [ ] Draft the ER diagram / table list for the entities in §5 — claimed by: — a diagram or table-by-table doc reviewed by the other two
- [ ] Write the PostgreSQL schema (tables, keys, constraints) for `mandi`, `commodity`/`variety`/`grade`, `commodity_alias`, `price_record` — claimed by: — schema applies cleanly to an empty database
- [ ] Write the schema for `rate_config`, `vehicle_class`, `distance_matrix` — claimed by: — schema applies cleanly, `rate_config` has source + effective_date columns per the working rule in claude.md
- [ ] Write the schema for `user`, `farmer_profile`, `listing`, `pool`, `pool_member` — claimed by: — schema applies cleanly

## Stage 2 — engine

Reference: `docs/ARCHITECTURE.md` §3.3. Plain Python, no DB access, no HTTP calls, no framework imports — takes values in, returns values out.

- [ ] `net_realisation` module — claimed by: — computes gross/commission/market_fee/handling/transport/net per the formula in §3.3, unit-tested against hand-computed values
- [ ] `vehicle_packing` module — claimed by: — given a quantity and vehicle classes, solves for cheapest vehicle combination; unit-tested including a capacity-boundary case
- [ ] `pool_split` module — claimed by: — splits pooled transport cost proportional to quantity, unit-tested

## Stage 3 — ingestion pipeline

Reference: `docs/ARCHITECTURE.md` §4. Runs on a schedule, separate from the request path.

- [ ] Fetch step — pull AGMARKNET data via data.gov.in API, paginated, per state/commodity — claimed by: —
- [ ] Validate + normalise steps — reject bad rows, map names to canonical IDs via alias table — claimed by: —
- [ ] Upsert step — insert/update on (mandi, commodity, variety, grade, date) — claimed by: —
- [ ] Derive step — recompute liquidity scores per §7 — claimed by: —
- [ ] Schedule it (cron / CI job) and log failures visibly (admin data-health screen can come later; logging can't) — claimed by: —

## Stage 4 — API layer

Reference: `docs/ARCHITECTURE.md` §3.2. No business arithmetic here — call the engine, don't reimplement it.

- [ ] Request/response models (Pydantic) for a mandi-ranking request — claimed by: —
- [ ] Auth — JWT + role-based checks (Farmer, Pool Coordinator permission, Admin) — claimed by: —
- [ ] Ranking endpoint — orchestrates repository fetch → engine call → response — claimed by: —
- [ ] Pool endpoints — create/join/lock a pool, following the lifecycle in §6 — claimed by: —

## Stage 5 — client

Reference: `docs/ARCHITECTURE.md` §3.1. React + Vite, i18n wired from the start.

- [ ] i18n scaffold (Punjabi, Hindi, English) wired before any screen is built — claimed by: —
- [ ] Ranking result screen — claimed by: —
- [ ] Pool creation/join flow — claimed by: —
- [ ] Deploy to Vercel, replacing the Stage 0 placeholder — claimed by: —

---

## Notes

- Update this file as tasks are claimed, finished, or split further. It's a working list, not a decision log — `docs/DECISIONS.md` is where the "why" behind a choice gets recorded permanently.
- If a task turns out to need something not yet decided, raise it before starting rather than guessing — check `docs/DECISIONS.md` first, then ask the group.
