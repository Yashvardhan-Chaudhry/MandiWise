# Tasks

Not role-based. We're three beginners building this together, so work is broken into concrete tasks instead of fixed ownership per person. Anyone can pick up any task. Claim a task by putting your name next to it before you start, so two people don't duplicate work.

Build order follows claude.md's "Next steps": schema → engine → API → client. Don't start a later stage's tasks until the stage before it has something working — the engine can't be tested without a schema to pull rate/distance data from, the API can't be tested without an engine, etc.

Format: `[ ] Task — claimed by: — what "done" looks like`

## Contribution under review — transport pooling system

The prepared contribution includes the transport backend, exact vehicle
selection/cost split, saved pool lifecycle, calculator and farmer-connection prototype
on `transport-pooling-system`. See
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

## Post-merge integration — added 2026-09-17

Three people's work was merged onto `main` in one week: the data pipeline
(`mandi_pull.py`, `ceda_pull.py`, `research/findings.md`), the recommendation engine
(`src/mandiwise/`) and the transport/pooling backend (`backend/`). These tasks are the
gaps that audit found at the seams. They are write-ups of problems, not fixes — nothing
below has been corrected yet.

Grouped by the module the work sits in, so the person who wrote a module can claim its
tasks first. Line references are to the code as merged on 2026-09-17.

### Recommendation engine — `src/mandiwise/` (Dhrity's module)

- [ ] Rebuild `net_realisation` in the canonical engine, adding the missing `market_fee` term — claimed by: — done looks like: the net figure subtracts commission, market fee (cess), handling and transport per `docs/ARCHITECTURE.md:60-66`; there is a field to carry the fee rate (`models.py` has none today, so `recommendation.py:49` computes gross − commission − handling − transport and every net figure in the repo is overstated by the cess); a test compares two mandis in different states and shows the ranking changes when their fee rates differ. See the canonical-engine decision dated 2026-09-17 in `docs/DECISIONS.md` — this is a rebuild in `backend/src/mandiwise_transport/engine.py`, not a patch to `recommendation.py`, and Dhrity's hand-verified worked example is its acceptance test.
- [ ] Carry reported min and max prices through to a net realisation range — claimed by: — done looks like: `PriceObservation` (`models.py:47-52`) carries min and max alongside modal; the engine returns a net figure **plus** the range `docs/ARCHITECTURE.md:68` requires, because modal is a typical outcome and not a guarantee; and ingestion validation step 2 (`docs/ARCHITECTURE.md` §4) can finally reject a row whose modal price falls outside its own reported min/max — which it cannot do today, because the fields are not read.
- [ ] Make the engine actually deterministic — claimed by: — done looks like: no `date.today()` call inside `src/mandiwise/` (`recommendation.py:37` has one, in a module documented as pure and deterministic); the reference day is always passed in; and every test passes `today=` explicitly (3 of the 4 do not, so they read the wall clock and their staleness assertions change meaning depending on the day they run).
- [ ] Fix the breakdown that does not add up — claimed by: — done looks like: the printed components sum exactly to the printed net. `recommendation.py:43-49` rounds each component to paise but computes net from the unrounded values, so a displayed breakdown can be off by about 2 paise against its own total. A farmer checking the arithmetic by hand must get the same answer the screen gives.
- [x] Key distances by mandi identity, not by name — claimed by: Yashvardhan — **done 2026-09-17** — done looks like: two offers for the same mandi name at different distances both keep their own distance. `recommendation.py:65` builds `distance_by_mandi` keyed on the mandi **name**, so duplicates collapse to one distance and the tie-break sorts on the wrong number.
- [ ] Test the optimiser with more than one vehicle type — claimed by: — done looks like: a test that a naive `ceil(quantity / capacity)` implementation would fail, plus a capacity-boundary case (a load one quintal over a vehicle's capacity). Today `tests/test_recommendation.py` defines `TRUCK` at line 16 and never uses it, so every existing test passes against a single-vehicle fleet and the multi-vehicle path is unverified.
- [ ] Decide and document the staleness threshold — claimed by: — done looks like: the "how old is stale" number appears in a project document (`docs/DOMAIN.md` or `docs/DECISIONS.md`) with a reason, and the code reads it from there. `recommendation.py:25` hardcodes `stale_after_days: int = 2`, a business threshold that no project document defines; the comparison is also strict `<`, so "stale after 2 days" actually means stale at 3 days or more — pick one meaning and make the name match it.

### Transport / pooling backend — `backend/` (Sarthak's module)

- [ ] Model Pool Coordinator as a permission, not a role — claimed by: — done looks like: the schema and the API match the 2026-08-20 decision "Pool Coordinator is a permission on a farmer account, not a separate user type". Today `db.py:38-40` has a `CheckConstraint` making role one of farmer/coordinator/admin — mutually exclusive — so `api.py:229-230` means a farmer cannot create a pool at all; `portal.py:113` registers every self-service user as `coordinator`, which makes `farmer` dead code in the portal; and `portal.py:240` applies a different authorisation rule than `api.py` does for the same action. Done means one rule for one action, a farmer can open a pool, and either the decision is implemented or a new dated entry in `docs/DECISIONS.md` supersedes it.
- [ ] Stop invented rates from persisting as sourced ones — claimed by: — done looks like: no path by which an unsourced number reaches a saved trip labelled as sourced. Today `web/static/vehicles.js:13-14` seeds four invented rate numbers, `pooling.js:125` puts that same editor on the **real** persisted trip-posting form, and the result is written with `is_demo=False` (`portal.py:271`) and the source string "Organizer-entered transport estimate" (`portal.py:242`) — which suppresses the synthetic-rates warning `services.py:76-79` would otherwise attach. The "rates-confirmed" required checkbox at `pooling.html:179-186` does not help: it is client-side only, `pooling.js:546-570` never reads or sends it, and `portal.Trip` has no field to store it. This is the "never fabricate a number" rule failing in the one place it matters — an assumption acquiring the appearance of a fact.
- [ ] Give a stuck pool a remedy — claimed by: — done looks like: a coordinator can always reach LOCKED or a clean cancellation. Today `services.py:150-154` refuses to lock if any participant's share exceeds their solo cost — reachable in normal use, because vehicle cost is a step function — while `api.py:332` refuses to re-review a member who is no longer PENDING and no remove-member endpoint exists. One approved member can therefore make a pool permanently un-lockable, with the only exits being that member voluntarily withdrawing or the whole trip being cancelled.
- [ ] Move the trip-cost formula into the engine — claimed by: — done looks like: `base + per_km × distance` exists in exactly one place, inside `engine.py`, and both call sites use it. It currently lives in `services.py:49-54` and again in `presentation.py:66`, and `presentation.py:77` sums totals in the route handler — against the working rule "business arithmetic lives in the engine. Not in route handlers, not in the client." Two copies of a formula is two formulas as soon as one is edited.
- [ ] Protect or unmount `POST /demo/calculate` — claimed by: — done looks like: the endpoint is either authenticated and rate-limited, or its router is mounted only by the local demo launcher. It is currently unauthenticated and unthrottled, mounted on the main app at `api.py:115`, and runs an O(quantity × vehicles) dynamic program that reaches roughly 1.2 million operations at the limits the API itself documents.
- [ ] Carry rate provenance through to the pooling UI — claimed by: — done looks like: a rate shown to a user is shown with its source, effective date and demo/real flag. `/v1` returns `rate_source`, effective dates and `is_demo`, but `pooling.js:383-438` and `portal.py:177-195` drop all three, so rates display bare — against "every price carries its reporting date" and against the project's own rule that rates are traceable to a source. The calculator view already does this correctly; the pooling view is where it is lost.

### Shared — either module

- [ ] Re-run the transport data review over the full corpus — claimed by: — done looks like: `docs/TRANSPORT_DATA_REVIEW.md` reports counts computed over all 12 files now in `data/`, not the 5 that existed when it was written. The document has a dated scope note saying what it was computed over; that note comes out when the numbers are recomputed. Reproduce with `python scripts/study_data.py --data-dir ../data` from `backend/`; do not estimate or scale the old figures.

## Internationalisation — added 2026-09-17

Scope, verification policy, numerals and RTL are settled in `docs/DECISIONS.md` (2026-09-17). These
tasks implement that decision; they do not re-open it. 13 locales: en, hi, pa, ur, mr, bn, gu, te,
ta, kn, ml, or, as. Only en/hi/pa get populated catalogues — the other ten are declared and stubbed.

- [ ] Locale registry + catalogue format — claimed by: — done looks like: one shared definition of the 13 locales (code, endonym, script, text direction) and a string-catalogue file format, usable by both the existing backend templates and the future React client, so adding a language is config rather than code
- [ ] English/Hindi/Punjabi catalogues populated and human-checked — claimed by: — done looks like: every user-facing string in those three locales checked by someone who reads the language, with a written record of who checked which
- [ ] Ten stub catalogues that fall back visibly — claimed by: — done looks like: ur, mr, bn, gu, te, ta, kn, ml, or, as are selectable but clearly marked as not yet translated, and untranslated strings fall back to English rather than rendering blank or as a raw key
- [ ] RTL layout support — claimed by: — done looks like: the page carries the correct `dir` for the active locale and the layout mirrors properly in Urdu; verified by eye on a narrow screen, not just asserted
- [ ] Latin numerals enforced across locales — claimed by: — done looks like: prices, quantities and distances render in Latin digits in every locale, including the Devanagari, Bengali and Perso-Arabic ones, with a test covering at least one non-Latin-script locale
- [ ] Retrofit i18n into the existing backend UI — claimed by: — done looks like: `backend/src/mandiwise_transport/web/templates/*.html` and the static JS no longer hardcode `<html lang="en">` or English strings; this is the "i18n from the first commit" rule being repaired, so it should land before more UI is written
- [ ] Commodity-name translation strategy — claimed by: — done looks like: a written decision on how commodity names are translated and verified, given `research/commodity_aliases.md` shows ~30% name disagreement between sources in English alone and the live feed carries mixed-script names; a wrong crop name costs a farmer real money, so this needs a plan before any non-English locale is marked available
- [ ] Update `docs/ARCHITECTURE.md` §3.1 — claimed by: — done looks like: the line naming "Punjabi, Hindi, English" reflects the 13-locale decision, since `claude.md` requires discrepancies between documents to be fixed rather than worked around

---

## Notes

- Update this file as tasks are claimed, finished, or split further. It's a working list, not a decision log — `docs/DECISIONS.md` is where the "why" behind a choice gets recorded permanently.
- If a task turns out to need something not yet decided, raise it before starting rather than guessing — check `docs/DECISIONS.md` first, then ask the group.
