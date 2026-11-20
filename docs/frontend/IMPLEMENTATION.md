# React frontend — 19 November 2026

> **Merged into `main` on 2026-11-19 (PR #4).** The branch names below describe how the work was developed; those branches have been deleted. Open follow-ups are in `docs/TASKS.md` under Stage 5.

Update: the subsequent `feature/net-realisation-frontend` branch integrates PR #1 and the ranking screen. See `NET_REALISATION_INTEGRATION.md`; statements below about missing ranking describe the earlier frontend checkpoint.

Branch: `feature/react-farmer-frontend`, based on local reviewed main `3eb7f7f`. Remote changes since that checkpoint were not checked in this implementation turn. No push or deployment performed. Backend code, original pages and the user's database are unchanged.

React + Vite follows ARCHITECTURE §3.1. Business arithmetic stays on the backend; React converts kg to display quintals and formats rupees only. The frontend calls the existing cookie-authenticated endpoints with their CSRF header and optimistic versions.

## Included

Overview, dated Punjab price browser with filters, editable transport calculator, registration/sign-in/sign-out, trip search/pagination, own trips, trip creation, join/approve/reject/withdraw controls, shares, lifecycle controls, approved-member chat, responsive layout and data/help page. No fake live prices, farmers or trips are seeded. New posted trips require caller-entered vehicle rates.

The 13-locale registry follows DECISIONS. Hindi/Punjabi labels are partial unverified previews; other untranslated locales explicitly fall back to English. Urdu sets RTL direction and numbers remain Latin. Some explanatory text remains English. Do not claim complete or human-verified translations.

## Verification

Production Vite build and frontend unit tests passed. Headless Chrome checks passed for: desktop, 390px mobile without document overflow, transport ₹3,700 / two ₹1,850 shares, market browser, Punjabi selection/Urdu direction, UI registration, UI trip creation, second-account join, organizer approval, quote, chat, lock and reload persistence. Unauthenticated chat returned 401; a foreign-origin authenticated write returned 403. Desktop/mobile screenshots were inspected.

Tests used a separate `work/react-frontend-validation.db`, never the user's `backend/portal.db`. Test servers stopped afterwards. Dispatch, settlement, cancellation, rejection and withdrawal are wired to existing endpoints but were not all exercised in this browser run. This is not exhaustive browser/security testing.

## Remaining release gates

- Net-return ranking API and associated input/result journey, including min/max scenarios. Price browsing is not a net recommendation.
- Current ingestion, canonical identities, verified fees, distances, rates and liquidity.
- Full translation catalog coverage and human review.
- Admin reference-data management UI.
- Known backend permission/provenance and un-lockable-pool issues in TASKS.
- Public deployment, identity/recovery/revocation and abuse controls.

The trip API has one district for both endpoints; the new form documents same-district trips until that contract changes. Frontend Punjab scope is not server-side enforcement. A browser checkbox does not verify a transport quote.

## Run

Start `START_MANDIWISE.cmd`, then `START_FRONTEND.cmd`. Keep both terminals open and visit http://127.0.0.1:5173. Use a private window or second profile for a second farmer. The new launcher does not replace the original launcher. See `frontend/README.md` for setup and hosting constraints. Describe this as the React frontend contribution, not a completed production product.
