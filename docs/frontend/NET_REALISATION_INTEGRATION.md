# Net-realisation frontend integration — 19 November 2026

Supersedes the earlier frontend notes that ranking has no API or screen. Earlier test and upload statements describe their own checkpoints.

## Branch and dependency

Branch: `feature/net-realisation-frontend`. Based on frontend commit `8a8e58d`, with Yash's PR #1 engine commit `e569e1b421e13ddd420caaecbe318f279530d1a1` and ranking UI commit `e9ce860`. On the subsequent upload pass, fetched origin and merged `origin/main` at `adc9da8` (Yash's merge of PR #1) into this branch without conflicts. The merge made no additional code changes because the engine commit was already present. Authorship is preserved; main is not modified by this contribution.

This branch includes the earlier React client from PR #2 as well as the ranking integration. Review it as the combined frontend contribution; avoid independently merging competing copies of the same work. It can be merged after PR #2 or reviewed against main as a combined change.

## User flow

The homepage primary action and navigation now lead to **Choose a mandi** (`#rankings`). Enter a reference starting village, crop and load in quintals; select up to ten Punjab mandi/district identities and enter road distances. The backend ranks all matching observations, and the client renders that order without doing financial arithmetic.

Results show the highest estimated net among submitted offers, alternatives, gross, commission, market fee, handling, transport, net, min/max net range, vehicle combination, variety/grade, distance, reporting date/age, stale styling, warnings and source/effective dates. Negative net values are preserved. Input changes clear old results; late responses from obsolete inputs are discarded. API failures and unmatched/empty results are visible. There is a link to existing farmer pooling; it does not claim pooled transport was used in the solo ranking.

## Contract and limits

- `GET /v1/commodities` supplies crop names; `GET /v1/markets?commodity=...` supplies mandi identities. Different districts remain distinct even when names match; multiple varieties at one identity share an entered distance.
- `POST /v1/rankings`: `{commodity, quantity_quintals, candidates: [{market, district, distance_km}]}`.
- Origin is a local reference label, not geocoded or transmitted as a routing input. Distances are manual; no invented defaults.
- The API does not accept farmer variety/grade filters. Offers keep the reported variety/grade and a compatibility warning. The screen does not claim to select the best reachable mandi across all Punjab or guarantee the farmer's grade-specific selling price.
- Snapshot prices and placeholder fees/vehicle rates are explicit. Market fee zero is unsourced and may overstate returns. No live recommendation, current liquidity, booking or forecast is claimed.
- Financial amounts stay in server-provided rupees; quantities are quintals at the boundary and kg/paise in the canonical backend.
- New strings are in the English translation catalogue, falling back under the existing unverified-locale notice. Human-reviewed Hindi/Punjabi translations remain pending.

## Run and verify

Restart the backend using `START_MANDIWISE.cmd`, then start/refresh `START_FRONTEND.cmd` and visit `http://127.0.0.1:5173/#rankings`. An old running backend will return 404 for rankings; the screen explains that it needs restarting with PR #1. The launcher's outdated statement that recommendations only exist as a CLI has been corrected.

Verification: 78 backend tests passed, one skipped; frontend tests and production build passed. Real-API Chrome checks covered ordering, breakdown and range values, stale labels, 390px mobile overflow, edited-input invalidation, crop-selection reset, API failure, discarding a late response, and the existing transport calculator. Isolated test database: `work/ranking-browser-validation.db`; user's portal database was not used. Visual review caught and corrected wrapped currency digits on narrow screens. Public deployment and hosted CI runs were not performed.

Next team steps: review/integrate this frontend branch, source actual rates/distances, add grade-compatible filtering in the API contract, then finish translation review and deployment. Do not replace Yash's engine with browser-side calculations.

## Alignment with Yash's handoff

Read `docs/handoff/SARTHAK_FRONTEND.md` from `origin/docs/report-and-handoffs` during upload preparation. Its first priority (ranking journey) is implemented here. Its next priorities remain: migrate the older price explorer from its bundled JSON/filter to the commodities/markets API, add report figures under `report/figures`, and obtain human translation verification. The ranking screen already uses the APIs; the old explorer still uses its original snapshot. Chat still uses manual refresh. Do not mark those remaining handoff items complete.

Proxy note: the existing client uses `changeOrigin: true` plus narrowly scoped translation of the two allowed local frontend Origin values to the backend origin. That differs from the handoff's simpler `changeOrigin: false` configuration but avoids its Host/Origin mismatch; prior real-cookie tests verified local writes succeed and foreign-origin writes fail. Keep this intentional distinction visible during integration review.
