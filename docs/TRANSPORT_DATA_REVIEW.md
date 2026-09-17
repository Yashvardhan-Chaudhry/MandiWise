# Transport backend: data review (2026-09-08)

> ## ⚠️ SCOPE NOTE — added 2026-09-17: these counts are historical, not current
>
> **What this document was computed over:** the **5** data files present in `data/` at
> commit `39657f9a20cf6d00e3be184d237571417ec7e9a9` — three CEDA commodity files
> (onion, potato, tomato) and the two Punjab live-feed snapshots. Every figure below,
> including the **8,866 record** total and the per-snapshot table, describes **that**
> snapshot of `data/` and nothing later.
>
> **What changed since:** a backfill (commit `e984cc3`, "Complete Patiala backfill: 8
> commodities, 2 years, with arrivals") more than doubled the corpus. `data/` now holds
> **12** files, and `research/findings.md` reports 16,907 historical rows plus 836
> live-feed rows for the current corpus.
>
> The counts below have **not** been recomputed and no figure here has been adjusted or
> estimated forward. Treat every number in this document as a measurement of the 5-file
> snapshot. Re-running the review over all 12 files is an open task in `docs/TASKS.md`
> ("Re-run the transport data review over the full corpus"); reproduce with
> `python scripts/study_data.py --data-dir ../data` from `backend/`. This note comes out
> when the numbers are recomputed.
>
> **The findings are not withdrawn.** The data-quality observations, the implications and
> the scope resolutions below were true of the files examined and nothing has contradicted
> them; only the record counts are known to be out of date.
>
> One other line has been overtaken: the closing bullet calls `research/findings.md` a
> pending report. It was written up on 2026-09-17 and is no longer pending; its
> conclusions are its own and are not restated here.

Read-only analysis of the five committed datasets at main commit
`39657f9a20cf6d00e3be184d237571417ec7e9a9`, plus README, architecture v0.1,
DECISIONS, TASKS, DOMAIN, IMPROVEMENTS, commodity aliases, both puller scripts,
and the supplied five-page MandiWise proposal. The shared Claude conversation was
not accessible (redirected to sign-in), so it is not a source for implementation choices.

Reproduce from `backend`: `python scripts/study_data.py --data-dir ../data`.
No new upstream requests were made; original data files are unchanged.

| Snapshot | Rows | Distinct market identities | Reporting days | Coverage |
|---|---:|---:|---:|---|
| CEDA onion (23) | 2680 | 7 | 710 | 2023-10-02 through 2025-10-30 |
| CEDA potato (24) | 2657 | 7 | 741 | 2023-10-02 through 2025-10-30 |
| CEDA tomato (78) | 2693 | 7 | 742 | 2023-10-02 through 2025-10-30 |
| Punjab 2026-09-04 | 386 | 34 | 1 | 2026-09-04 |
| Punjab 2026-09-07 | 450 | 40 | 1 | 2026-09-07 |

Total: **8866 records**, of which 8030 are historical CEDA records and 836 are
two current-feed snapshots. Market identity is `(state, district, market)`.
Reporting days are distinct dates across the commodity dataset, not evidence that
every mandi reported on each day.

## Data quality observations

- Every CEDA record has an empty grade. These records cannot establish grade-specific returns.
- Arrival quantities are present in 2508 onion, 2460 potato and 2481 tomato records.
  These are historical market arrivals, not farmer lot weights, available trucks or current demand.
- Two potato rows and one tomato row violate `min <= modal <= max`.
- One tomato row repeats the complete price-record identity
  `(state, district, market, commodity, variety, grade, arrival_date)`.
- Eleven September 4 and twelve September 7 rows have modal prices below the existing
  Rs 50/quintal analysis floor. Both live snapshots have valid min/modal/max ordering.
- The current-feed files expose 57 distinct commodity strings together (as also documented
  in commodity_aliases.md). Source names must not be treated as canonical cross-source IDs.
- None of the five files contains coordinates, road distances, vehicle payload limits,
  supplier quotes, rate validity, fleet availability or farmer readiness/location data.

## Implications for this implementation

The transport module can use live-feed market names as an exact, source-labelled
catalogue. It cannot learn or truthfully seed actual vehicle prices, routes or road
factors from these files. Rate and route creation therefore require explicit provenance
and date validity. Synthetic rates exist only in tests and the opt-in demonstration.

No historical price or arrival volume is used in vehicle allocation. Farmers declare
their own current quantity and lot details. Historical CEDA datasets remain untouched;
the existing decision log's non-commercial-use/attribution constraints still apply.

## Scope resolutions for review

- User's current request specifically authorises a transport backend. This builds only
  its database, engine and API slice; it does not implement the entire project schema.
- Use the architecture's **quantity-proportional transport cost split**. The proposal's
  wording about distributing savings would be a different mathematical rule.
- A 120-quintal load must not fit into a 100-quintal truck. The optimiser handles whole
  combinations and exposes excess capacity; the proposal example is not an input rate card.
- One shared pickup and mandi/date per pool. Additional farm collection and multi-stop
  routing are excluded from quoted cost and explicitly reported as such.
- Never silently claim bookings or real fleet availability. Coordinators arrange transport.
- Pool lock rejects a participant cost increase even if the group saves overall.
  This is a new conservative policy proposed for team review.
- `research/findings.md` remains a pending economic-validation report. This inventory
  does not establish that travelling further is profitable or that pooling improves
  real-world returns without sourced transport and fee data.
