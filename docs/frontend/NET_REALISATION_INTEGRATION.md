# Net-realisation frontend integration — 19 November 2026

Supersedes the earlier frontend notes that ranking has no API or screen. Earlier test and upload statements describe their own checkpoints.

## Branch and dependency

Local branch: `feature/net-realisation-frontend`. Based on frontend commit `8a8e58d`, with Yash's open PR #1 merged locally at `e569e1b421e13ddd420caaecbe318f279530d1a1`. This preserves his authorship and incorporates the canonical engine, ranking API, data configuration and appended decisions. It does not merge or close PR #1 on GitHub and does not change main. Coordinate upstream merge order with Yash (his API first).

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

Next team steps: land/review PR #1, integrate this frontend branch, source actual rates/distances, add grade-compatible filtering in the API contract, then finish translation review and deployment. Do not replace Yash's engine with browser-side calculations.
