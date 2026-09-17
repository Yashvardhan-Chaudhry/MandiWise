# Transport-engine benchmark — engine A vs engine B

**Date:** 2026-09-17
**Branch:** `main`, post-merge (`af72340 Merge transport pooling system from Sarthak`)
**Harness:** `research/engine_benchmark.py` — standard library only, seeded, deterministic

## Reproduce

```bash
python research/engine_benchmark.py
```

From the repository root. No arguments, no network, no database. Runs in about 40 seconds.
Two consecutive runs were diffed: every line except wall-clock timings was byte-identical.

---

## What was measured

The repo now contains two independent solutions to the same problem — pack a quantity into
whole vehicles at least cost.

| | Engine A | Engine B |
|---|---|---|
| Location | `src/mandiwise/transport.py::cheapest_transport_plan` | `backend/src/mandiwise_transport/engine.py::optimise` |
| Author | Dhrity | Sarthak |
| Quantity unit | `Decimal` quintals | `int` kilograms |
| Money unit | `Decimal` rupees, exact | `int` paise |
| Algorithm | exhaustive recursive enumeration | unbounded-covering dynamic programme |
| Cost model | base + per-km × distance, computed inside | one flat trip price per vehicle, supplied by the caller |
| Tie-break | lowest cost, then least spare capacity | lowest cost, then fewest vehicles, then least spare capacity, then vehicle code |

Engine B imported cleanly from `backend/src` with no framework or database import — as it is
documented to. Nothing had to be worked around.

### The unit bridge

Everything in this report depends on one conversion, so it is stated explicitly:

```
1 quintal = 100 kg      quintals × 100 → kg
1 rupee   = 100 paise   rupees   × 100 → paise
trip cost = base_cost_inr + per_km_cost_inr × distance_km
```

Engine B prices a *trip*, so distance has to be folded into the vehicle's unit cost before it is
handed over. The harness asserts each bridged value is a whole kilogram and a whole paisa, and
counts any that are not. **Bridge failures across all 3,000 randomised trials: 0.** No result below
is contaminated by a conversion artefact.

---

## Experiment 1 — differential correctness

3,000 randomised `(quantity, distance, fleet)` triples, seed `20260917`. Each triple is fed to both
engines in their own units and the **total cost** is compared. Fleets are 2–4 distinct vehicle
types drawn from capacities 5–100 q, base costs 0–3,000 INR, per-km rates 0–30 INR in 0.50 steps,
distances 0–200 km, quantities 0.25–60.00 q in 0.25 q steps. Draws are rejected and redrawn if
engine A's predicted search would exceed 2,000 leaves, or if a vehicle's trip cost would be zero
(engine B rejects a free vehicle).

| Measure | Result |
|---|---|
| Cost disagreements | **0 of 3,000** |
| Unit-bridge failures | 0 |
| Fleet-composition differences at identical cost | 2 of 3,000 |
| Engine A time | 10.0 s total, 3.34 ms/call |
| Engine B time | 17.5 s total, 5.83 ms/call |

**Both engines are correct on cost, everywhere the harness could compare them.** Engine A's
exhaustive search agreed with engine B's dynamic programme on every single trial. That is the
result I expected on reading the code, and it is worth saying why: engine A's `vehicle_limit`
bound — `ceil(quantity / smallest capacity)` — is genuinely sound. No optimal solution can use
more units of any type than that, because every vehicle costs something and any surplus unit could
be dropped while still covering the load. The search is therefore exhaustive over a superset of the
optimum, which is exactly what it claims to be. No bug found in either engine on cost.

The two fleet-composition differences are not errors. Both engines found the same minimum cost and
picked different vehicle mixes to achieve it; their documented tie-break rules differ (engine A
prefers less spare capacity, engine B prefers fewer vehicles first). Whichever rule the product
wants should be picked deliberately, but neither is wrong today.

Note on the timings above: engine B is slower here, and that is not a defect. This experiment
deliberately lives in the small-quantity, few-types corner where engine A is affordable, and engine
B's cost is O(quantity_kg × types) — it pays for every one of the 6,000 kg cells regardless of how
easy the instance is. The scaling picture reverses completely; see experiment 2.

### Sub-paisa probe

Not a randomised case — a single deliberate one. With per-km rates of 10.0007 and 20.0007 INR
(40 q, 60 km):

- engine A: INR 3200.0840
- engine B: INR 3200.08
- difference: INR 0.0040, same fleet chosen

This is a **representation difference, not a packing difference**. Engine A carries exact Decimal
rupees; engine B's integer-paise model cannot express a fraction of a paisa and rounds half-up. It
is invisible with the current placeholder rate card (whole rupees), but it becomes real the moment
a sourced rate card with per-km paise lands in `transport_rate_card`. Worth a line in
`DECISIONS.md` about which representation the project adopts.

---

## Experiment 2 — scaling in the number of vehicle types

Distance fixed at 60 km. The rate card is generated deterministically (capacity 20 q, 25 q, 30 q …;
cost rising with size) so the only variable is how many distinct classes exist. These are
placeholder figures, like everything else in `data/vehicle_rates.json`.

Engine A's search evaluates exactly `(vehicle_limit + 1) ** n_types` leaves, which is knowable
before the call. The harness computes that number in advance and **does not attempt** any call
above 400,000 leaves. That cap is why this run cannot hang; it is also why one cell below is empty.

| Quantity | Types | Engine A leaves | Engine A time | Engine B ops | Engine B time | A / B |
|---:|---:|---:|---:|---:|---:|---:|
| 5 q | 2 | 4 | 0.0001 s | 1,000 | 0.0008 s | 0.1× |
| 5 q | 5 | 32 | 0.0010 s | 2,500 | 0.0018 s | 0.6× |
| 5 q | 8 | 256 | 0.0139 s | 4,000 | 0.0025 s | 5.6× |
| 5 q | 12 | 4,096 | 0.3056 s | 6,000 | 0.0064 s | 48× |
| 20 q | 2 | 4 | 0.0001 s | 4,000 | 0.0032 s | 0.0× |
| 20 q | 5 | 32 | 0.0012 s | 10,000 | 0.0067 s | 0.2× |
| 20 q | 8 | 256 | 0.0127 s | 16,000 | 0.0101 s | 1.3× |
| 20 q | 12 | 4,096 | 0.2713 s | 24,000 | 0.0142 s | 19× |
| 50 q | 2 | 16 | 0.0002 s | 10,000 | 0.0069 s | 0.0× |
| 50 q | 5 | 1,024 | 0.0432 s | 25,000 | 0.0152 s | 2.8× |
| 50 q | 8 | 65,536 | 3.3680 s | 40,000 | 0.0259 s | 130× |
| 50 q | 12 | 16,777,216 | **not attempted** | 60,000 | 0.1287 s | — |

- **Last size engine A completed:** 8 types at 50 quintals — 65,536 leaves in **3.37 s**.
- **Measured engine A throughput:** 18,757 leaves/second.
- **12 types at 50 quintals:** 16,777,216 leaves. Extrapolating from that measured throughput gives
  roughly **894 seconds (~15 minutes)** for a single call. That figure is an extrapolation, not a
  measurement — the call was never run.
- Cost mismatches among the 11 pairs that both engines completed: **0**.

Read plainly: below about 5 vehicle types, engine A is the faster of the two and the difference is
immaterial either way. At 8 types and a 50 q load it takes 3.4 seconds, which is already past what
belongs in a request path. At 12 types it is out of reach. Engine B's worst cell in the whole grid
is 0.13 s. The rate card in the repo today has 2 vehicle classes, where engine A costs 0.0002 s —
so this is a headroom question, not a present-day failure.

---

## Experiment 3 — the project's worked example

40 quintals of potato, the canonical rate card from `data/vehicle_rates.json` (Tempo: 30 q, base
INR 1,000, INR 10/km; Truck: 100 q, base INR 2,500, INR 20/km), at the two distances in
`data/example_market_prices.csv`. That rate card carries its own warning: *"PLACEHOLDER RATE CARD —
NOT SOURCED."*

| Mandi | Distance | Engine A | Engine B | Fleet (both) | Agree |
|---|---:|---:|---:|---|---|
| Mandi A (local) | 20 km | INR 2,400 | INR 2,400 | 2 × Tempo | yes |
| Mandi B (distant) | 60 km | INR 3,200 | INR 3,200 | 2 × Tempo | yes |

Identical cost and identical fleet. The demo figures the project has been showing are reproduced
by both implementations independently.

---

## Experiment 4 — real price rows

`data/*.json` read the way `mandi_pull.py::load_snapshots` reads it: a snapshot is a list of row
dicts, anything else is skipped out loud. `vehicle_rates.json` was correctly skipped as not a price
snapshot.

- rows loaded after de-duplication: **17,742**
- passing the ARCHITECTURE §4 validation (date parses, modal > 0, min ≤ modal ≤ max): **17,737**
  (5 rejected)
- Patiala district: **16,928**
- Patiala markets present: Dudhansadhan, Ghanaur, Ghanaur APMC, Nabha, Patiala, Patiala APMC,
  Patran, Rajpura, Samana

Side observation, not part of the brief: **19 rows pass validation with a modal price below
INR 10/quintal** (e.g. Patti APMC brinjal at INR 0.18). The min/max bracket the modal, so §4's rule
accepts them, and they flow through to a large negative net realisation. §4 validation is not
sufficient on its own.

### 4a. Does the `recommendation.py:65` name-key bug fire?

Line 65 builds `distance_by_mandi = {offer.price.mandi_name: offer.distance_km for offer in offers}`
and line 68 looks distances up from it. Two offers with the same mandi *name* collapse to one entry
— last one wins.

Scanned across every same-day, same-commodity cross-section in the real data:

| | Count |
|---|---:|
| Cross-sections with 2+ offers, Punjab-wide | 4,780 |
| …in which one market name appears twice | **4** |
| Cross-sections with 2+ offers, Patiala only | 4,701 |
| …in which one market name appears twice | **0** |
| Distinct market names appearing in more than one district | **0** |

So the key collision **does fire on real data — four times.** All four are one market reporting two
varieties of the same commodity on the same day:

| Date | Commodity | Market | The two rows |
|---|---|---|---|
| 04/09/2026 | Brinjal | Nakodar APMC (Jalandhar) | Round INR 1,150 · Brinjal INR 800 |
| 04/09/2026 | Onion | Tanda Urmur APMC (Hoshiarpur) | Other INR 4,200 · Nasik INR 4,900 |
| 07/09/2026 | Brinjal | Nakodar APMC (Jalandhar) | Brinjal INR 750 · Other INR 1,250 |
| 07/09/2026 | Colacasia | Ludhiana APMC (Ludhiana) | Other INR 2,500 · Arabi INR 1,700 |

In each, `distance_by_mandi` ends up with one fewer key than there are offers. **But in these four
cases the harm is zero**, and it is worth being precise about why: both colliding rows are the same
physical market, so they carry the same distance, so the collapsed entry is still the right number.
`rank_mandis` returned both rows in the correct net-realisation order (e.g. Ludhiana APMC at ranks
1 and 4 of 6 on 07/09). No Patiala cross-section collides at all, and no market name in the whole
17,742-row set appears in two districts.

To show that the bug is real rather than theoretical, the harness includes one **constructed**
reproduction — labelled as constructed in the output, because the feed does not contain a case with
this shape. Two mandis sharing the name "Ghanaur", priced so their net realisations tie exactly at
INR 42,580:

```
offers            : Ghanaur @111 km (INR 1250/q) listed first
                    Ghanaur @15 km  (INR 1200/q) listed second
distance_by_mandi : {'Ghanaur': '15'}     2 offers -> 1 key
transport paid    : INR 4220.00 (returned first), INR 2300.00 (returned second)
```

Both rows now sort on the same collapsed distance, so the documented *"ties favour the nearer
mandi"* rule becomes inert, `sorted` falls back to input order, and the farther mandi — the one
with INR 1,920 more transport — is returned first. Keying the lookup by offer identity (index or
`id()`) rather than by name fixes it in one line.

**Verdict:** the bug is real and the fix is cheap, but it is currently latent. It becomes live the
moment the data includes two mandis sharing a name (two districts, or the alias table mapping
variants together), or offers for one mandi at different distances. The feed's own naming is
already unstable in the other direction — "Ghanaur" and "Ghanaur APMC", "Patiala" and "Patiala
APMC" both appear as separate names in Patiala — which is the same class of problem, and is why
`ARCHITECTURE.md` §5 keys `price_record` on a mandi ID and not a name.

### 4b. The missing `market_fee` term

`ARCHITECTURE.md` lines 60–66 specify:

```
net = gross − commission − market_fee − handling − transport
```

`calculate_recommendation` computes `gross − commission − handling − transport`. The `market_fee`
term is absent, so every net realisation the engine reports is **too high** by `gross × fee_rate`.

Quantified across all 16,928 valid Patiala rows, for a 40 q lot, using the commission rate (4%) and
handling charge (INR 30/quintal) carried in `data/example_market_prices.csv` — a file that labels
its own figures *"Illustrative project example - not government data"* — and holding distance at
20 km, because no sourced origin→mandi distance matrix exists yet (`ARCHITECTURE.md` §8):

Net realisation as currently computed: median INR 65,520 · min INR 2,160 · max INR 457,200.

> **The fee rates below are ASSUMED ILLUSTRATIVE PROBES. They are not sourced, and they are not
> Punjab's actual market fee. Nobody has looked that up. They exist only to give the size of the
> error a scale.**

| Assumed fee rate | Median fee per 40 q lot | Median overstatement of net | Worst row | Rows pushed below zero |
|---:|---:|---:|---:|---:|
| 1% | INR 720 | 1.10% | 2.78% | 0 |
| 2% | INR 1,440 | 2.20% | 5.56% | 0 |
| 3% | INR 2,160 | 3.30% | 8.33% | 0 |

At an assumed 2%, a farmer is told he keeps about 2.2% more than he would — around INR 1,440 on a
typical 40-quintal lot. The worst rows (low price, so the fixed handling and transport eat a large
share of net) are overstated by more than twice that.

Does the omission change *which* mandi wins? Not necessarily — the fee is proportional to gross, so
omitting it is arithmetically the same as using a commission rate that is too low by the fee rate,
and that does not cancel out against transport and handling. On the repo's own two-mandi example,
the winner does not change:

| | Mandi B (distant) | Mandi A (local) |
|---|---:|---:|
| as computed today | INR 48,592 | INR 42,480 |
| with 1% assumed fee | INR 48,040 | INR 42,000 |
| with 2% assumed fee | INR 47,488 | INR 41,520 |
| with 3% assumed fee | INR 46,936 | INR 41,040 |
| with 25% assumed fee | INR 34,792 | INR 30,480 |

The distant mandi's higher gross means it pays more fee, but here it earns enough more to stay
ahead even at an absurd 25%. So in this example the fee affects the *number shown to the farmer*,
not the *ranking*. That is not a general guarantee — it is one example with two rows.

---

## What this adds up to

1. **Engine A's cost results are correct.** 3,000 randomised comparisons, zero cost disagreements,
   and the worked example reproduces exactly. Its search bound is sound, not lucky.
2. **Engine A's algorithm is exponential in the number of vehicle classes, and that is measurable
   rather than theoretical**: 0.0002 s at 2 classes, 3.37 s at 8, unreachable at 12. Engine B is
   0.13 s at the worst point on the grid. With today's 2-class rate card this costs nothing; a
   12-class rate card would make engine A unusable in a request path.
3. **Two engines, one problem.** The project has duplicate implementations of
   `vehicle_packing` (`ARCHITECTURE.md` §3.3 names one module). This benchmark says they agree, so
   the choice can be made on other grounds — scaling, units, tie-break policy — rather than on
   correctness. That choice is not made here and belongs in `DECISIONS.md`.
4. **One confirmed bug:** `recommendation.py:65` keys distances by mandi name. It fires on 4 real
   cross-sections today with no ill effect, and misorders tied results the moment two offers share
   a name at different distances.
5. **One confirmed spec gap:** `calculate_recommendation` omits `market_fee`, overstating net
   realisation by `gross × fee_rate` on every single row — roughly 2.2% at an assumed 2%. The real
   rate is unknown; sourcing it is the blocking step, not the code change.

### Limits of this benchmark

- The randomised comparison is confined to 2–4 vehicle types and ≤60 quintals, because engine A
  cannot be exercised beyond that at 3,000 trials. Agreement at larger fleet sizes is **not**
  established by this run.
- One grid cell in experiment 2 was never run; its cost is an extrapolation and is labelled as one.
- Every rate, distance and fee used here is a placeholder. Open risk #2 in `claude.md` is untouched
  by this work.
- Engine A was compared on cost only. Its `TransportPlan` fleet composition was recorded but, where
  it differs from engine B's at equal cost, no judgement is made about which tie-break is better.
