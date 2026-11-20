# Demo brief — read this before we present

Five-minute read. Its purpose: **all three of us tell the same story, and none of us claims something
a teammate's answer contradicts.** That, more than a rough edge in the UI, is how a demo actually
goes wrong.

The demo script is `docs/DEMO_RUNBOOK.md`. The written version of this story is the IEEE report,
`report/mandiwise.tex`. The two must agree.

*Updated 2026-11-20 for the second presentation. The September version said there was no React
client and quoted 55 tests. Both are out of date; use this file.*

---

## The one-sentence story

> We tested whether the idea was true before building on it. It is: same crop, same day, nearby
> mandis differ by 73.1% at the median across 2,821 comparisons. We built the whole decision tool
> on that footing. One input stands between the premise and the product claim: real transport and
> fee rates.

Everything below supports that sentence.

---

## Numbers that are safe to say

All are measured and reproducible from committed data. Sources: `research/findings.md`,
`research/engine_benchmark.md`, and the output of `python research/report_figures.py`.

| Figure | Value | Where it comes from |
|---|---|---|
| Median price dispersion | **73.1%** | 2,821 same-day comparisons |
| Interquartile range | 46.7%–113.9% | same |
| Comparisons below our 10% "strong" bar | 1.2% | bar set *before* we measured |
| Median spread by crop | 50.0% (tomato) to 92.6% (cauliflower) | historical data, 8 crops |
| Potato, cheapest vs dearest mandi | median weekly gap 81.1% over 107 weeks | 7 Patiala mandis |
| Rows analysed | 17,742 | 16,907 historical + 836 live, one duplicate dropped |
| Historical span | 2023-10-02 → 2025-10-30 | 7 Patiala mandis × 8 crops |
| Liquidity | median 21 of 30 reporting days | 18 of 45 mandi–crop pairs below 60% |
| Engine benchmark | 0 cost disagreements in 3,000 trials | at 8 vehicle types: 3.37 s vs 0.0259 s |
| Pooling example | 40 q alone ₹3,200; two × 40 q pooled ₹1,850 each | placeholder rate card |
| Ranking example | Mandi B ₹48,592 vs Mandi A ₹42,480 | `python demo.py` and the API agree |
| Tests | **90 passing** | 78 backend (+1 PostgreSQL test skipped locally) + 5 root + 7 frontend |

**Do not round these upward, and do not quote a number that isn't on this list.** If you don't
remember one, say "it's in our findings document". That is a perfectly good answer.

---

## Who owns what

**Yashvardhan: data, validation, engine rebuild, integration.**
- Built two pullers and the validation analysis.
- Rebuilt net realisation in the canonical engine, adding the market fee and the min/max range, and
  wrote the ranking API.
- Ran the integration audit, the decision log and the report.
- *Decision worth defending:* reject bad rows rather than clean them. One mandi published placeholder
  prices of ₹0.08–₹32.90 on both live days; we log and drop those rows.
- *Does not do:* scheduled ingestion. Pulls are still manual.

**Dhrity: first recommendation engine, backend hardening.**
- Wrote the first net-realisation engine (`src/mandiwise/`).
- *Decision worth defending:* `Decimal` throughout and validation on every input. Her hand-verified
  worked example (₹41,880 / ₹42,792) is now the acceptance test of the rebuilt engine.
- *Now:* fixing the backend defects from the audit (`docs/handoff/DHRITY_BACKEND.md`).

**Sarthak: transport/pooling backend and the React client.**
- Built the FastAPI service, the schema and migrations, and the packing DP and cost split.
- Built the React client: ranking screen, explorer, calculator and pooling.
- *Decision worth defending:* the pool lifecycle is enforced on the server, and the client does no
  money arithmetic. It shows the server's figures exactly. Cost splits by quantity, never by sale
  value.
- *Does not do yet:* the Coordinator is a role rather than a permission (a logged task). Hindi and
  Punjabi strings are partial and unchecked.

---

## Hard questions, honest answers

**"Are these rates real?"**
No. Transport, commission and fee rates are labelled placeholders. Every ranking response and the
screen say so. The engine has every term, so real rates are a data change, not a code change.
Sourcing them is our blocking next step.

**"So have you proven farmers make more money?"**
No. We've proven the **premise**: nearby mandis differ by 73% at the median. The **product claim**
is about net realisation after real costs, and that needs sourced rates. The fee matters too: a 3%
fee flips our own worked example, and a test asserts that.

**"Why were there two engines?"**
Two of us solved the same problem independently. We benchmarked them against each other over 3,000
randomised cases and found zero disagreements on cost. We chose the DP on scaling: at 8 vehicle
types it takes 0.0259 s against 3.37 s. The reasoning is recorded.

**"What's your test coverage?"**
There are 90 automated tests, run in CI on every pull request, including a PostgreSQL job. They are
uneven: the backend is well covered, the pullers only by a compile check.

**"Show me the multilingual UI."**
The React client has a 13-locale registry and right-to-left Urdu. Hindi and Punjabi are partial and
not yet checked by a speaker, so we don't present any language as verified. That policy is
deliberate: a wrong crop name costs a farmer money.

**"What went wrong during the project?"**
Answer confidently, not defensively:
- The government API silently drops requests whose User-Agent mentions Python.
- A second source returns an empty result instead of an error when it throttles you.
- About 30% of crop names disagree between sources.
- Our first presentation looked unfinished, so we rebuilt the UI in React and tied every screen to
  the tested engine.

---

## Do not claim

Read this list. One person overclaiming is the main risk.

- ❌ That net realisation is proven. It is not.
- ❌ That any rate is real. Transport, commission and fee are placeholders; the fee is 0.
- ❌ That the liquidity signal works on live data. We have 2 live days.
- ❌ That the multilingual UI is finished, or that hi/pa are verified.
- ❌ That it runs on PostgreSQL in the demo. The demo runs on SQLite; PostgreSQL runs in CI.
- ❌ That the prices on screen are current. They are September 2026 snapshots, flagged as stale.
- ❌ That it is deployed. It runs locally.
- ❌ Any number not in the table above.

If you don't know, say **"I don't know, let me check."** With a decision log and a task backlog in
the repo, that answer looks organised. A confident wrong answer that a teammate then contradicts
does not.

---

## Before the day

- [ ] Everyone has read this document and the report.
- [ ] Agree who says what, and who fields questions about which module.
- [ ] Agree our line on how we used AI tooling, so all three answers match. Each of us must be
      able to explain any code we're credited with.
- [ ] One full rehearsal against a clock, using `docs/DEMO_RUNBOOK.md`.
