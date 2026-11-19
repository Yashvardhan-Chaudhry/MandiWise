# Handoff — Sarthak — React client

Date: 2026-11-19 · From: Yashvardhan · Status: open

This brief covers only what the existing docs don't. For everything else, read
`docs/ARCHITECTURE.md` §3.1 (client), the `docs/DECISIONS.md` 2026-09-17 i18n entries,
`docs/TASKS.md` (Stage 5 and "Internationalisation"), `backend/README.md` and
`docs/transport/DEVELOPMENT.md`.

## 1. Goal and scope

The last presentation went badly partly because the frontend looked unfinished. This client
fixes that, and its screens go into today's IEEE report as figures. Screens:

- **(a) Mandi ranking**: new, and the headline feature
- **(b) Transport calculator**: replaces `/demo`
- **(c) Pooling**: browse trips, trip detail, join/approve/withdraw, lifecycle, chat, post trip (replaces `/pooling`)
- **(d) Sign in and register**, **(e) Language switcher**

## 2. Where and how

- `frontend/` at the repo root. Vite + React. TypeScript is your call.
- Node 24 is installed. `node_modules/` and `dist/` are already in `.gitignore`.
- Start the backend with `backend\.venv\Scripts\python.exe -m mandiwise_transport.presentation` (port 8001).
- The dev server proxies the API so requests are same-origin and the cookie, `X-MandiWise-Request` and Origin checks pass:

```js
// frontend/vite.config.js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backend = { target: "http://127.0.0.1:8001", changeOrigin: false };

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/v1": backend, "/portal": backend, "/demo": backend, "/health": backend },
  },
});
```

> **Keep `changeOrigin: false`.** `portal.py` `check_origin()` compares the browser's `Origin`
> with `request.base_url`, which comes from the `Host` header. With `changeOrigin: true`,
> `Host` becomes `127.0.0.1:8001` while `Origin` stays `localhost:5173`, and every POST gets 403 `bad_origin`.

- Send these with every request: `credentials: "same-origin"`, `Content-Type: application/json` and
  `X-MandiWise-Request: portal`. For an example, see `api()` in `backend/src/mandiwise_transport/web/static/pooling.js`.
- Errors come back as `{"error": {"code", "message"}}`. Pydantic 422s instead return `{"detail": [...]}`
  (`pooling.js` handles both). Show the `message` in the UI and branch on the `code`.

## 3. Existing endpoints the client needs (checked against the code)

Auth: **none** = public; **cookie** = `mandiwise_session` cookie. Every non-GET request with a
cookie also needs the header and a matching Origin.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | none | Liveness check |
| POST | `/portal/api/register` | none + header | `{username, password, name, village}`. Sets the cookie. |
| POST | `/portal/api/login` | none + header | `{username, password}`. Sets the cookie. |
| POST | `/portal/api/logout` | header | Clears the cookie |
| GET | `/v1/me` | cookie | `{id, name, role}`. A 401 means signed out. |
| POST | `/demo/calculate` | none | Stateless calculator: `{distance_km, farmers[1–8]{name, quantity_quintals}, vehicles[1–12]{code, name?, capacity_quintals, base_cost_inr, per_km_inr}}` |
| GET | `/demo/vehicles.js` | none | Default vehicle presets used by the old page (JS, not JSON) |
| GET | `/portal/api/trips?search=&travel_date=&offset=&limit=` | none | OPEN future trips (summary objects) |
| GET | `/portal/api/mine` | cookie | Trips I organise or have joined |
| POST | `/portal/api/trips` | cookie | Post a trip: route, vehicles, own lot (auto-approved) |
| GET | `/portal/api/trips/{id}` | none | Trip summary |
| GET | `/portal/api/trips/{id}/workspace` | cookie | Full pool view with member names and `version` (empty members if not a participant) |
| POST | `/v1/pools/{id}/join` | cookie | `{quantity_quintals, variety, grade, condition}`. Sets the member to PENDING. |
| POST | `/v1/pools/{id}/members/{mid}/review` | cookie | Organiser: `{expected_version, decision: APPROVED\|REJECTED}` |
| POST | `/v1/pools/{id}/withdraw` | cookie | `{expected_version}` |
| POST | `/v1/pools/{id}/quote` | cookie | Cost split. The organiser sees everyone; a member sees only their own row. |
| POST | `/v1/pools/{id}/transition` | cookie | `{expected_version, target, transport_reference?, note?}`. Paths: OPEN→LOCKED/CANCELLED, LOCKED→DISPATCHED/CANCELLED, DISPATCHED→SETTLED. DISPATCHED needs `transport_reference`. SETTLED and CANCELLED need a `note`. |
| GET / POST | `/portal/api/trips/{id}/messages` | cookie | Chat: last 100 messages / `{body ≤1000}`. Only approved members and the organiser. Read-only once SETTLED or CANCELLED. |

## 4. New endpoints: build against this contract, mock until merged

Built and tested on branch `engine/net-realisation-rankings` — **PR #1**. Until it merges, run the backend from that branch (`git worktree add ../mw-engine engine/net-realisation-rankings`) or use mocks. The shapes below match the code (`backend/tests/test_rankings.py` pins them).
Money is a **decimal string in rupees**, quantities are in **quintals**, and dates are **ISO `YYYY-MM-DD`**.
**Field names could still change in PR review.** Keep all API types and fetchers in one module
(e.g. `src/api.ts`) so a rename is one edit. Keep mock fixtures beside it.

- `GET /v1/commodities` (none) → `{"commodities": ["Potato", ...], "source": str, "warnings": [str]}`.
  Lists the commodity names present in the committed AGMARKNET snapshots.
- `GET /v1/markets?commodity=Potato` (none) → `{"as_of", "stale_after_days": 2, "source", "rejected_rows": {"unparseable", "below_floor", "outside_min_max"}, "markets": [{"market", "district", "state", "commodity", "variety", "grade", "price_date", "age_days", "is_stale", "min_price", "modal_price", "max_price"}], "warnings"}`.
  Returns the latest observation per (market, variety, grade).
- `POST /v1/rankings` (none, input-capped)
  - Body: `{"commodity", "quantity_quintals": "40", "candidates": [{"market", "district": str|null, "distance_km": "60"}]}`
  - Limits: 1–10 candidates, quantity ≤ 1000 q, distance ≤ 2000 km.
  - Returns `{"as_of", "is_demo": true, "commodity", "quantity_quintals", "price_source", "stale_after_days", "rates": {"source", "effective_from", "commission_bp", "market_fee_bp", "handling_per_quintal"}, "vehicle_rates": {"source", "effective_from"}, "warnings", "results": [...], "unmatched": [{"market", "reason"}]}`.
  - Each result: `{"rank", "market", "district", "state", "variety", "grade", "price_date", "age_days", "is_stale", "distance_km", "modal_price", "min_price", "max_price", "gross", "commission", "market_fee", "handling", "transport", "net", "net_min", "net_max", "vehicles": [{"code", "name", "count"}]}`.
  - Sanity check for your mocks: `Near APMC` ₹1200 at 20 km vs `Far APMC` ₹1380 at 60 km, 40 q → Far ranks 1st, net `48592.00` (range `45520.00`–`51280.00` with min/max 1300/1450), Near net `42480.00` — the same figures `python demo.py` prints.
  - Errors: 422 for invalid input (FastAPI `detail[]`), 429 `slow_down` past 30 ranking calls/min per client, 503 `prices_unavailable` if no snapshots are found.
  - The breakdown always sums exactly: `net = gross − commission − market_fee − handling − transport`. `net_min` and `net_max` come from the reported min and max prices.

## 5. Non-negotiables

- [ ] **No business arithmetic in the client.** Show server numbers exactly as returned. Never recompute net, shares or totals. See `CLAUDE.md` working rules and ARCHITECTURE §2.
- [ ] **Every price shows its `price_date`.** Stale prices appear greyed with an "old price" label and are never hidden. See `CLAUDE.md` working rules.
- [ ] **Show where the rates come from.** Display `rates.source`/`effective_from` and `vehicle_rates.source`/`effective_from`. Show a visible **PLACEHOLDER** banner whenever `is_demo` is true or `warnings` is not empty. See `CLAUDE.md` open risk #2.
- [ ] **Net is a range.** Show `net_min – net_max` next to `net`, not a single number on its own.
- [ ] **i18n from the first commit.** The registry holds 13 locales (en, hi, pa, ur, mr, bn, gu, te, ta, kn, ml, or, as), each with `code`, `endonym`, `script` and `dir`. Only en, hi and pa are populated. The other ten are visibly marked "not yet translated" and fall back to English. See DECISIONS 2026-09-17 and TASKS "Internationalisation".
- [ ] **hi and pa need a human check before they are marked available.** Record who checked which catalogue in the repo. See DECISIONS 2026-09-17.
- [ ] **Latin digits in every locale.** Use e.g. `new Intl.NumberFormat(locale + "-u-nu-latn")` with en-IN grouping (`1,00,000`). Add a test for one non-Latin-script locale. See DECISIONS 2026-09-17.
- [ ] **RTL.** For `ur`, set `dir="rtl"` (and `lang`) on `<html>` and mirror the layout. Use CSS logical properties (`margin-inline-start`, etc.), not left/right. See DECISIONS 2026-09-17.
- [ ] **Low-end Android first.** Keep the bundle small (no heavy UI kit), use touch targets of 44px or more, and make numbers large and readable. See ARCHITECTURE §3.1.
- [ ] **Translate enum labels.** Show pool states (OPEN, LOCKED, DISPATCHED, SETTLED, CANCELLED) and member states (PENDING, APPROVED, REJECTED, WITHDRAWN) as translated labels, never raw enums.
- [ ] **In-app dialogs.** No `prompt()` or `confirm()`. The old `pooling.js` uses them for withdraw and the transition notes.
- [ ] **URL routing.** Refresh and back must work, e.g. `/rank`, `/calculator`, `/trips`, `/trips/:id`, `/signin`.

## 6. Backend quirks to design around

- **Restarts log everyone out.** The session secret is regenerated on each restart unless `JWT_SECRET` is set (`presentation.py` `create_demo_app`). Treat a 401 from `/v1/me` as signed out, without an error screen. Set `JWT_SECRET` while capturing screenshots.
- **Password length is 15–128 characters on register.** Username matches `^[a-z0-9_]{3,40}$`. Validate both on the form and show the rule in advance.
- **Login and register are throttled to 10 per minute per IP** (429 `slow_down`). Chat allows 60 per minute and posting trips 20 per minute.
- **Chat has no push.** Poll while the chat is open (e.g. every 10 s) and add a refresh button.
- **Every portal registration is created with role `coordinator`.** Dhrity is fixing the role-vs-permission model. Don't hard-code role checks. Decide what to show from `/v1/me` plus whether `organizer_id` / `coordinator_id` equals your user id.
- **Write calls need `expected_version`.** It comes from `/workspace`. A 409 `version_conflict` means reload the workspace and retry. Don't retry blindly.
- **Pool and trip endpoints return quantities as `*_kg` integers.** Displaying them in quintals is a unit conversion only, never money. Ask for `*_quintals` fields in the API if you'd rather not convert.
- **LOCKED is refused** if any member is PENDING (`pending_members`) or if a member would pay more than travelling alone (`member_cost_increase`). Show the server's message.

## 7. Report figures: by end of today if possible, in this order

Save the PNGs to `report/figures/` (the folder doesn't exist yet; create it). Make them at least 1600 px wide, light theme, with realistic data.

1. `fig_ranking.png`: ranking result with the breakdown, net range, price dates and the PLACEHOLDER banner
2. `fig_calculator.png`: calculator showing the vehicle step function and the per-farmer split
3. `fig_pool_detail.png`: pooling trip detail with members and the cost split
4. `fig_i18n_hi.png`: one screen in Hindi or Punjabi
5. `fig_i18n_ur.png`: one screen in Urdu showing the RTL mirroring

If the rankings PR hasn't merged, capture `fig_ranking.png` from the mock. Its caption must then say so.

## 8. Workflow

- [ ] Branch `frontend/react-client`. Commit under your own GitHub account; git history is the contribution evidence.
- [ ] Open a PR to `main` (protected, one approval).
- [ ] Add `frontend/README.md` with the steps to install, run the dev server against the backend, and build.
- [ ] Claim the Stage 5 tasks and the relevant Internationalisation tasks in `docs/TASKS.md` with your name.
- [ ] Leave the old `backend/src/mandiwise_transport/web/` pages alone. Don't delete them in this PR; they go once the React client covers them.

---

## Progress — Sarthak's report (received 2026-11-19)

Pushed as `feature/react-farmer-frontend` (`8a8e58d`), opened as **PR #2**. Yashvardhan checked it
locally: `npm ci`, `npm test` (6/6) and `npm run build` all pass, and it touches no backend file.
Built: overview, dated price explorer, transport calculator, accounts, trip discovery and own trips,
trip creation, join/approve/reject/withdraw, quotes, lifecycle controls, chat, help page, a
13-locale registry with partial unverified hi/pa, and Urdu RTL. Hash routes; responsive.
Browser-tested against an isolated database (desktop and 390 px).

**Next, in this order** (everything else in this brief still applies):
1. **Ranking journey on `POST /v1/rankings`** (§4; PR #1). Input: crop, quantity, 1–10 candidate
   mandis with distance. Show net with its `net_min`–`net_max` range, the full breakdown, price
   date and stale flag, the vehicles, the `unmatched` list, and every `warnings` entry as a
   visible banner. This is the headline screen the last demo lacked.
2. **Switch the price explorer to `GET /v1/commodities` + `GET /v1/markets`** and delete
   `marketRows` and the `data/punjab_2026-09-07.json` import. The server already rejects
   sub-₹50 and out-of-order rows and returns `rejected_rows`. Keeping a JS copy of that rule is
   duplicated business logic, and it ships about 100 kB of JSON in the bundle.
3. **Screenshots for the report** (§7): at minimum the ranking screen and one desktop and one
   mobile shot of the current client, saved as `report/figures/fig_ranking.png`,
   `fig_react_desktop.png` and `fig_react_mobile.png`. Your existing
   `MandiWise-React-Desktop.png` / `-Mobile.png` can go in now under the last two names.
4. Keep hi/pa labelled unverified until a speaker checks them, and record who checked.
