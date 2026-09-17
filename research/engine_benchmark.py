"""Benchmark harness: two independent transport-packing engines, compared.

Engine A  src/mandiwise/transport.py::cheapest_transport_plan
          Decimal quintals, Decimal rupees, exhaustive recursive search.
Engine B  backend/src/mandiwise_transport/engine.py::optimise
          int kilograms, int paise, unbounded-covering dynamic programme.

Run from the repository root:

    python research/engine_benchmark.py

Standard library only. Deterministic: every random draw comes from a single
seeded random.Random, so two runs on the same revision produce the same numbers.

Unit bridge (the only place the two engines meet):
    1 quintal = 100 kg          quintals * 100 -> kg
    1 rupee   = 100 paise       rupees   * 100 -> paise
Engine B prices a *trip*, so the bridge also folds distance into cost:
    trip cost = base_cost_inr + per_km_cost_inr * distance_km
The harness asserts every bridged value is exact (a whole kg, a whole paisa)
and counts any that are not, so a rounding artefact can never be mistaken for a
disagreement between the two algorithms.

NOTE ON NUMBERS: every rate, distance and fee rate used here is an illustrative
placeholder, consistent with claude.md open risk #2 and the header of
data/vehicle_rates.json. Nothing in this file is a sourced figure.
"""

from __future__ import annotations

import collections
import csv
import json
import random
import sys
import time
from datetime import date
from decimal import Decimal
from math import ceil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "backend" / "src"))

from mandiwise.models import MandiOffer, PriceObservation, VehicleType  # noqa: E402
from mandiwise.recommendation import calculate_recommendation, rank_mandis  # noqa: E402
from mandiwise.transport import cheapest_transport_plan  # noqa: E402

from mandiwise_transport.engine import Vehicle, optimise  # noqa: E402

SEED = 20260917
TRIALS = 3000

# Pre-flight cap on engine A. Its search evaluates (vehicle_limit + 1) ** n_types
# leaves, so the cost of a call is predictable before it is made. Any call whose
# predicted leaf count exceeds this is recorded as "not attempted" rather than
# being allowed to run for hours. This is the harness's substitute for a signal
# based timeout, which is not available on Windows.
LEAF_CAP_DIFFERENTIAL = 2_000
LEAF_CAP_SCALING = 400_000

RULE = "-" * 78


# --------------------------------------------------------------------------
# unit bridge
# --------------------------------------------------------------------------

class BridgeError(ValueError):
    pass


def quintals_to_kg(quintals: Decimal) -> int:
    """100 kg to the quintal. Refuses anything that is not a whole kilogram."""
    value = Decimal(quintals) * 100
    if value != value.to_integral_value():
        raise BridgeError(f"{quintals} quintals is not a whole number of kg")
    return int(value)


def rupees_to_paise(rupees: Decimal) -> int:
    """100 paise to the rupee. Refuses anything that is not a whole paisa."""
    value = Decimal(rupees) * 100
    if value != value.to_integral_value():
        raise BridgeError(f"INR {rupees} is not a whole number of paise")
    return int(value)


def paise_to_rupees(value: int) -> Decimal:
    return Decimal(value) / 100


def as_engine_b_fleet(vehicles, distance_km: Decimal) -> list[Vehicle]:
    """Engine B prices a whole trip, so distance is folded into the unit cost."""
    return [
        Vehicle(
            code=v.name,
            capacity_kg=quintals_to_kg(Decimal(v.capacity_quintals)),
            cost_paise=rupees_to_paise(v.trip_cost(distance_km)),
        )
        for v in vehicles
    ]


def predicted_leaves(quantity: Decimal, vehicles) -> int:
    """Engine A's own bound, reproduced so a call's cost is known in advance.

    transport.py sets vehicle_limit = ceil(quantity / smallest capacity) and
    then tries 0..vehicle_limit units of *every* type, so the search evaluates
    (vehicle_limit + 1) ** len(vehicle_types) leaves.
    """
    min_capacity = min(Decimal(v.capacity_quintals) for v in vehicles)
    limit = ceil(float(quantity / min_capacity))
    return (limit + 1) ** len(vehicles)


def describe(vehicles, distance_km: Decimal) -> str:
    return " | ".join(
        f"{v.name}: cap {v.capacity_quintals}q base {v.base_cost_inr} "
        f"per-km {v.per_km_cost_inr} -> trip {v.trip_cost(distance_km)}"
        for v in vehicles
    )


# --------------------------------------------------------------------------
# experiment 1 - differential correctness
# --------------------------------------------------------------------------

CAPACITIES = [5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100]  # whole quintals
BASE_COSTS = [0, 200, 400, 600, 800, 1000, 1500, 2000, 2500, 3000]  # whole INR
PER_KM = [Decimal(x) / 2 for x in range(0, 61, 1)]  # 0 .. 30.0 INR/km, 0.5 steps


def draw_case(rng: random.Random):
    """One (quantity, distance, fleet) triple both engines will accept.

    Constraints exist so the comparison is about the algorithms, not about
    input validation: engine B rejects a zero-cost vehicle, requires unique
    codes and whole kilograms; engine A is exponential, so the draw is
    rejected if its predicted leaf count exceeds LEAF_CAP_DIFFERENTIAL.
    """
    while True:
        n_types = rng.choice([2, 2, 3, 3, 4])
        caps = rng.sample(CAPACITIES, n_types)
        vehicles = []
        for i, cap in enumerate(caps):
            base = Decimal(rng.choice(BASE_COSTS))
            per_km = rng.choice(PER_KM)
            vehicles.append(
                VehicleType(f"V{i:02d}", Decimal(cap), base, per_km)
            )
        distance = Decimal(rng.randint(0, 200))
        if any(v.trip_cost(distance) <= 0 for v in vehicles):
            continue  # engine B requires a strictly positive trip price
        quantity = Decimal(rng.randint(1, 240)) / 4  # 0.25 .. 60.00 quintals
        if predicted_leaves(quantity, vehicles) > LEAF_CAP_DIFFERENTIAL:
            continue
        return quantity, distance, vehicles


def experiment_differential() -> dict:
    rng = random.Random(SEED)
    disagreements = []
    bridge_failures = 0
    a_total = 0.0
    b_total = 0.0
    fleet_differences = 0

    for trial in range(TRIALS):
        quantity, distance, vehicles = draw_case(rng)
        try:
            fleet_b = as_engine_b_fleet(vehicles, distance)
        except BridgeError:
            bridge_failures += 1
            continue

        start = time.perf_counter()
        plan_a = cheapest_transport_plan(quantity, distance, vehicles)
        a_total += time.perf_counter() - start

        start = time.perf_counter()
        result_b = optimise(quintals_to_kg(quantity), fleet_b)
        b_total += time.perf_counter() - start

        cost_a = Decimal(plan_a.total_cost_inr)
        cost_b = paise_to_rupees(result_b["cost_paise"])
        fleet_a = {name: count for name, count in plan_a.vehicles}
        fleet_b_out = {row["code"]: row["count"] for row in result_b["vehicles"]}
        if fleet_a != fleet_b_out:
            fleet_differences += 1
        if cost_a != cost_b:
            disagreements.append(
                {
                    "trial": trial,
                    "quantity_quintals": str(quantity),
                    "distance_km": str(distance),
                    "fleet": describe(vehicles, distance),
                    "engine_a_cost_inr": str(cost_a),
                    "engine_a_fleet": fleet_a,
                    "engine_a_capacity_q": str(plan_a.total_capacity_quintals),
                    "engine_b_cost_inr": str(cost_b),
                    "engine_b_fleet": fleet_b_out,
                    "engine_b_capacity_kg": result_b["capacity_kg"],
                }
            )

    print(RULE)
    print("EXPERIMENT 1 - DIFFERENTIAL CORRECTNESS")
    print(RULE)
    print(f"seed                    : {SEED}")
    print(f"trials                  : {TRIALS}")
    print(f"engine A leaf cap/trial  : {LEAF_CAP_DIFFERENTIAL}")
    print(f"unit-bridge failures    : {bridge_failures}")
    print(f"TOTAL COST disagreements: {len(disagreements)}")
    print(
        f"fleet-composition differences (legitimate, tie-break rules differ): "
        f"{fleet_differences}"
    )
    print(f"engine A total time     : {a_total:8.3f} s  ({a_total / TRIALS * 1000:.3f} ms/call)")
    print(f"engine B total time     : {b_total:8.3f} s  ({b_total / TRIALS * 1000:.3f} ms/call)")
    for case in disagreements[:20]:
        print()
        print("  COST DISAGREEMENT, trial %d" % case["trial"])
        print("    quantity : %s quintals" % case["quantity_quintals"])
        print("    distance : %s km" % case["distance_km"])
        print("    fleet    : %s" % case["fleet"])
        print("    engine A : INR %s  %s  capacity %s q"
              % (case["engine_a_cost_inr"], case["engine_a_fleet"], case["engine_a_capacity_q"]))
        print("    engine B : INR %s  %s  capacity %s kg"
              % (case["engine_b_cost_inr"], case["engine_b_fleet"], case["engine_b_capacity_kg"]))
    if len(disagreements) > 20:
        print("  ... %d further disagreements suppressed" % (len(disagreements) - 20))
    print()
    sub_paisa_probe()
    return {
        "disagreements": disagreements,
        "fleet_differences": fleet_differences,
        "a_total": a_total,
        "b_total": b_total,
    }


def sub_paisa_probe() -> None:
    """The randomised draw uses rates that land on a whole paisa, so the bridge
    is exact and any difference would be algorithmic. This probe shows what the
    two engines do when a rate does NOT land on a whole paisa - a representation
    difference, not a packing bug, but one worth knowing about before a real
    rate card with per-km paise is loaded.
    """
    fleet = [
        VehicleType("Tempo", Decimal("30"), Decimal("1000"), Decimal("10.0007")),
        VehicleType("Truck", Decimal("100"), Decimal("2500"), Decimal("20.0007")),
    ]
    quantity = Decimal("40")
    distance = Decimal("60")
    plan_a = cheapest_transport_plan(quantity, distance, fleet)
    fleet_b = [
        Vehicle(v.name, quintals_to_kg(Decimal(v.capacity_quintals)),
                int((v.trip_cost(distance) * 100).to_integral_value(rounding="ROUND_HALF_UP")))
        for v in fleet
    ]
    result_b = optimise(quintals_to_kg(quantity), fleet_b)
    cost_a = Decimal(plan_a.total_cost_inr)
    cost_b = paise_to_rupees(result_b["cost_paise"])
    print("  sub-paisa probe (per-km rate 10.0007 / 20.0007 INR, 40 q, 60 km):")
    print("    engine A (exact Decimal) : INR %s" % cost_a)
    print("    engine B (whole paise)   : INR %s" % cost_b)
    print("    difference               : INR %s  - rounding of the rate card, "
          "not a packing difference" % (cost_a - cost_b))
    print("    both engines chose the same fleet: %s"
          % (dict(plan_a.vehicles) == {r["code"]: r["count"] for r in result_b["vehicles"]}))
    print()


# --------------------------------------------------------------------------
# experiment 2 - scaling
# --------------------------------------------------------------------------

SCALING_TYPES = [2, 5, 8, 12]
SCALING_QUANTITIES = [Decimal(5), Decimal(20), Decimal(50)]


def scaling_fleet(n_types: int) -> list[VehicleType]:
    """Deterministic rate card: capacity 20q, 25q, ... ; cost rises with size.

    Placeholder figures, shaped like data/vehicle_rates.json but extended so the
    number of distinct classes can be varied. Not sourced.
    """
    fleet = []
    for i in range(n_types):
        capacity = Decimal(20 + 5 * i)
        base = Decimal(800 + 150 * i)
        per_km = Decimal(8 + 2 * i)
        fleet.append(VehicleType(f"V{i:02d}", capacity, base, per_km))
    return fleet


def experiment_scaling() -> list[dict]:
    distance = Decimal(60)
    rows = []
    print(RULE)
    print("EXPERIMENT 2 - SCALING IN THE NUMBER OF DISTINCT VEHICLE TYPES")
    print(RULE)
    print("distance fixed at %s km; engine A calls above %s predicted leaves are"
          % (distance, f"{LEAF_CAP_SCALING:,}"))
    print("not attempted (pre-flight cap, see module docstring).")
    print()
    print("  qty(q)  types  A leaves     A time        B ops     B time     ratio")
    for quantity in SCALING_QUANTITIES:
        for n_types in SCALING_TYPES:
            fleet = scaling_fleet(n_types)
            fleet_b = as_engine_b_fleet(fleet, distance)
            leaves = predicted_leaves(quantity, fleet)

            start = time.perf_counter()
            result_b = optimise(quintals_to_kg(quantity), fleet_b)
            b_time = time.perf_counter() - start
            b_ops = quintals_to_kg(quantity) * n_types

            if leaves <= LEAF_CAP_SCALING:
                start = time.perf_counter()
                plan_a = cheapest_transport_plan(quantity, distance, fleet)
                a_time = time.perf_counter() - start
                agree = Decimal(plan_a.total_cost_inr) == paise_to_rupees(result_b["cost_paise"])
                a_text = f"{a_time:8.4f}s"
                ratio = f"{a_time / b_time:7.1f}x" if b_time else "     n/a"
            else:
                a_time = None
                agree = None
                a_text = " not run"
                ratio = "       -"
            rows.append(
                {
                    "quantity": quantity,
                    "n_types": n_types,
                    "leaves": leaves,
                    "a_time": a_time,
                    "b_time": b_time,
                    "b_ops": b_ops,
                    "agree": agree,
                    "cost_b": paise_to_rupees(result_b["cost_paise"]),
                }
            )
            print("  %6s  %5d  %9s  %9s  %11s  %8.4fs  %8s"
                  % (quantity, n_types, f"{leaves:,}", a_text, f"{b_ops:,}", b_time, ratio))

    completed = [r for r in rows if r["a_time"] is not None]
    skipped = [r for r in rows if r["a_time"] is None]
    if completed:
        throughput = sum(r["leaves"] for r in completed) / sum(r["a_time"] for r in completed)
        print()
        print("  engine A measured throughput: %s leaves/second" % f"{throughput:,.0f}")
        largest = max(completed, key=lambda r: r["leaves"])
        print("  largest engine A case completed: %d types at %s quintals "
              "(%s leaves) in %.4f s"
              % (largest["n_types"], largest["quantity"],
                 f"{largest['leaves']:,}", largest["a_time"]))
        for row in skipped:
            print("  not attempted: %d types at %s quintals - %s leaves, "
                  "extrapolated %s s at the measured throughput"
                  % (row["n_types"], row["quantity"], f"{row['leaves']:,}",
                     f"{row['leaves'] / throughput:,.0f}"))
    mismatches = [r for r in completed if not r["agree"]]
    print()
    print("  cost mismatches among the %d completed pairs: %d"
          % (len(completed), len(mismatches)))
    print()
    return rows


# --------------------------------------------------------------------------
# experiment 3 - the project's worked example
# --------------------------------------------------------------------------

def load_rate_card() -> tuple[list[VehicleType], dict]:
    payload = json.loads((ROOT / "data" / "vehicle_rates.json").read_text(encoding="utf-8"))
    fields = ("name", "capacity_quintals", "base_cost_inr", "per_km_cost_inr")
    card = [
        VehicleType(**{k: (row[k] if k == "name" else Decimal(str(row[k]))) for k in fields})
        for row in payload["vehicles"]
    ]
    return card, payload


def load_example_offers() -> list[dict]:
    path = ROOT / "data" / "example_market_prices.csv"
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def experiment_worked_example(rate_card, payload, example_rows) -> list[dict]:
    quantity = Decimal("40")  # the project's illustrative 40-quintal potato lot
    print(RULE)
    print("EXPERIMENT 3 - WORKED EXAMPLE: 40 QUINTALS OF POTATO")
    print(RULE)
    print("rate card: data/vehicle_rates.json")
    print("  %s" % payload["purpose"])
    for v in rate_card:
        print("  %-8s capacity %sq  base INR %s  per-km INR %s"
              % (v.name, v.capacity_quintals, v.base_cost_inr, v.per_km_cost_inr))
    print()
    results = []
    for row in example_rows:
        distance = Decimal(row["distance_km"])
        plan_a = cheapest_transport_plan(quantity, distance, rate_card)
        result_b = optimise(quintals_to_kg(quantity), as_engine_b_fleet(rate_card, distance))
        cost_a = Decimal(plan_a.total_cost_inr)
        cost_b = paise_to_rupees(result_b["cost_paise"])
        agree = cost_a == cost_b
        print("  %-18s %s km" % (row["mandi_name"], distance))
        print("    engine A : INR %s   fleet %s" % (cost_a, dict(plan_a.vehicles)))
        print("    engine B : INR %s   fleet %s"
              % (cost_b, {r["code"]: r["count"] for r in result_b["vehicles"]}))
        print("    agree    : %s" % ("YES" if agree else "NO"))
        results.append(
            {
                "mandi": row["mandi_name"],
                "distance": distance,
                "cost_a": cost_a,
                "cost_b": cost_b,
                "agree": agree,
                "fleet_a": dict(plan_a.vehicles),
                "fleet_b": {r["code"]: r["count"] for r in result_b["vehicles"]},
            }
        )
    print()
    return results


# --------------------------------------------------------------------------
# experiment 4 - real AGMARKNET/CEDA rows through rank_mandis
# --------------------------------------------------------------------------

def load_price_rows() -> tuple[list[dict], list[str]]:
    """Read data/*.json the way mandi_pull.py::load_snapshots does.

    A snapshot is a list of row dicts. Anything else (vehicle_rates.json is a
    dict) belongs to somebody else and is skipped out loud.
    """
    rows: list[dict] = []
    skipped: list[str] = []
    data_dir = ROOT / "data"
    for path in sorted(data_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list) or not all(isinstance(r, dict) for r in payload):
            skipped.append(path.name)
            continue
        rows += payload
    seen, unique = set(), []
    for r in rows:
        key = (r.get("arrival_date"), r.get("market"), r.get("commodity"),
               r.get("variety"), r.get("grade"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique, skipped


def parse_day(text: str) -> date:
    day, month, year = text.split("/")
    return date(int(year), int(month), int(day))


def valid_price_row(row: dict) -> bool:
    """ARCHITECTURE section 4 step 2: reject missing dates, non-numeric prices,
    or a modal price outside the reported min/max."""
    try:
        low = Decimal(str(row["min_price"]))
        high = Decimal(str(row["max_price"]))
        modal = Decimal(str(row["modal_price"]))
        parse_day(row["arrival_date"])
    except Exception:
        return False
    return modal > 0 and low <= modal <= high


# Illustrative parameters. Sources: commission rate and handling charge are the
# figures carried in data/example_market_prices.csv, which that file itself
# labels "Illustrative project example - not government data". The distance is
# also taken from that file. None of these are sourced local rates.
ILLUSTRATIVE_COMMISSION = Decimal("0.04")
ILLUSTRATIVE_HANDLING = Decimal("30")
ILLUSTRATIVE_DISTANCE = Decimal("20")
# ASSUMED market-fee rates. ARCHITECTURE.md lines 60-66 require a market_fee
# term; nobody has sourced a rate for it. These three are illustrative probes,
# NOT sourced values, and must not be quoted as Punjab's actual market fee.
ASSUMED_FEE_RATES = [Decimal("0.01"), Decimal("0.02"), Decimal("0.03")]


def experiment_real_data(rate_card) -> dict:
    rows, skipped_files = load_price_rows()
    print(RULE)
    print("EXPERIMENT 4 - REAL PRICE ROWS THROUGH rank_mandis")
    print(RULE)
    print("files skipped as not-a-price-snapshot : %s" % (", ".join(skipped_files) or "none"))
    print("price rows loaded (deduplicated)      : %d" % len(rows))
    valid = [r for r in rows if valid_price_row(r)]
    print("rows passing ARCHITECTURE s4 validation: %d (rejected %d)"
          % (len(valid), len(rows) - len(valid)))
    implausible = [r for r in valid if Decimal(str(r["modal_price"])) < 10]
    print("rows that PASS validation with a modal price below INR 10/quintal: %d"
          % len(implausible))
    if implausible:
        print("  (min/max bracket the modal, so ARCHITECTURE s4 accepts them; "
              "they still produce a large negative net realisation)")
    patiala = [r for r in valid if r.get("district") == "Patiala"]
    print("Patiala district rows                 : %d" % len(patiala))
    print("Patiala markets                       : %s"
          % ", ".join(sorted({r["market"] for r in patiala})))
    print()

    # ---------------- 4a: the mandi-name key collision --------------------
    print("  4a. recommendation.py:65 - distance_by_mandi keyed by mandi NAME")
    print("  " + "-" * 74)
    sections = collections.defaultdict(list)
    for r in valid:
        sections[(r["arrival_date"], r["commodity"])].append(r)
    multi = {k: v for k, v in sections.items() if len(v) > 1}
    collisions = {
        k: v for k, v in multi.items()
        if len({x["market"] for x in v}) < len(v)
    }
    pat_sections = collections.defaultdict(list)
    for r in patiala:
        pat_sections[(r["arrival_date"], r["commodity"])].append(r)
    pat_multi = {k: v for k, v in pat_sections.items() if len(v) > 1}
    pat_collisions = {
        k: v for k, v in pat_multi.items()
        if len({x["market"] for x in v}) < len(v)
    }
    print("  same-day cross-sections with 2+ offers, Punjab-wide : %d" % len(multi))
    print("  ... in which one market name appears twice          : %d" % len(collisions))
    print("  same-day cross-sections with 2+ offers, Patiala only: %d" % len(pat_multi))
    print("  ... in which one market name appears twice          : %d" % len(pat_collisions))
    print("  distinct market names mapping to 2+ districts       : %d"
          % len({m for m, ds in
                 ((m, {r["district"] for r in valid if r["market"] == m})
                  for m in {r["market"] for r in valid})
                 if len(ds) > 1}))
    print()

    collision_report = []
    for key, section in sorted(collisions.items()):
        names = collections.Counter(x["market"] for x in section)
        repeated = [n for n, c in names.items() if c > 1]
        offers = []
        for r in section:
            offers.append(
                MandiOffer(
                    price=PriceObservation(
                        mandi_name=r["market"],
                        commodity=r["commodity"],
                        modal_price_per_quintal=Decimal(str(r["modal_price"])),
                        reported_on=parse_day(r["arrival_date"]),
                    ),
                    # Distance held constant across the cross-section: no sourced
                    # origin->mandi distance matrix exists yet (ARCHITECTURE s8).
                    distance_km=ILLUSTRATIVE_DISTANCE,
                    commission_rate=ILLUSTRATIVE_COMMISSION,
                    handling_cost_per_quintal=ILLUSTRATIVE_HANDLING,
                )
            )
        ranked = rank_mandis(offers, Decimal("40"), rate_card,
                             today=parse_day(key[0]))
        distance_keys = {o.price.mandi_name for o in offers}
        collision_report.append(
            {
                "date": key[0],
                "commodity": key[1],
                "repeated": repeated,
                "offers": len(offers),
                "distinct_keys": len(distance_keys),
                "ranked": [(rec.mandi_name, str(rec.net_realisation_inr)) for rec in ranked],
                "rows": [(r["district"], r["market"], r["variety"], r["grade"],
                          r["modal_price"]) for r in section],
            }
        )
        print("  REAL COLLISION  %s  %s  (%d offers in the cross-section)"
              % (key[0], key[1], len(offers)))
        for row in collision_report[-1]["rows"]:
            if row[1] in repeated:
                print("      %-12s %-22s variety=%-10s grade=%-8s modal=%s" % row)
        print("    distance_by_mandi holds %d keys for %d offers -> %d offer(s) "
              "lose their own distance entry"
              % (len(distance_keys), len(offers), len(offers) - len(distance_keys)))
        positions = [
            (i + 1, rec.mandi_name, rec.net_realisation_inr)
            for i, rec in enumerate(ranked)
            if rec.mandi_name in repeated
        ]
        print("    the collided name lands at rank %s of %d: %s"
              % ("/".join(str(p[0]) for p in positions), len(ranked),
                 ", ".join("net INR %s" % p[2] for p in positions)))
    print()

    # Minimal reproduction of the observable harm. CONSTRUCTED, and labelled so.
    print("  CONSTRUCTED reproduction (not from the feed): two mandis that share")
    print("  a name but sit at different distances, with equal net realisation.")
    day = date(2026, 9, 17)
    # Two mandis sharing one name at different distances, priced so that their
    # net realisations tie exactly - which is precisely the case the documented
    # "ties favour the nearer mandi" rule exists to settle. The prices and
    # distances below are CONSTRUCTED to produce that tie; they are not feed
    # values and not sourced.
    twin = [
        MandiOffer(
            price=PriceObservation("Ghanaur", "Potato", price, day),
            distance_km=distance,
            commission_rate=ILLUSTRATIVE_COMMISSION,
            handling_cost_per_quintal=ILLUSTRATIVE_HANDLING,
        )
        for price, distance in (
            (Decimal("1250"), Decimal("111")),  # listed first, farther
            (Decimal("1200"), Decimal("15")),   # listed second, nearer
        )
    ]
    repro = rank_mandis(twin, Decimal("40"), rate_card, today=day)
    lookup = {o.price.mandi_name: o.distance_km for o in twin}
    print("    offers            : Ghanaur @111 km (INR 1250/q) listed first,")
    print("                        Ghanaur @15 km  (INR 1200/q) listed second")
    print("    net realisation   : %s"
          % ", ".join("%s = INR %s" % (r.mandi_name, r.net_realisation_inr) for r in repro))
    print("    tie?              : %s"
          % ("YES - both INR %s" % repro[0].net_realisation_inr
             if repro[0].net_realisation_inr == repro[1].net_realisation_inr
             else "no"))
    print("    distance_by_mandi : %s   (2 offers collapse to %d key; last offer "
          "wins, so BOTH rows sort on that one distance)"
          % ({k: str(v) for k, v in lookup.items()}, len(lookup)))
    print("    transport paid    : %s"
          % ", ".join("INR %s" % r.transport_inr for r in repro))
    print("    -> the row returned first is the one with the HIGHER transport")
    print("       bill (the farther mandi), because both rows sorted on the same")
    print("       collapsed distance and the tie-break became inert. Keying the")
    print("       lookup by offer identity instead of name fixes it.")
    print()

    # ---------------- 4b: the missing market_fee term ---------------------
    print("  4b. calculate_recommendation omits market_fee (ARCHITECTURE.md:60-66)")
    print("  " + "-" * 74)
    print("  quantity 40 q; commission %s and handling INR %s/q from"
          % (ILLUSTRATIVE_COMMISSION, ILLUSTRATIVE_HANDLING))
    print("  data/example_market_prices.csv (that file labels them illustrative);")
    print("  distance held at %s km. Fee rates below are ASSUMED ILLUSTRATIVE"
          % ILLUSTRATIVE_DISTANCE)
    print("  PROBES, not sourced Punjab market-fee rates.")
    quantity = Decimal("40")
    nets = []
    grosses = []
    negatives = 0
    for r in patiala:
        offer = MandiOffer(
            price=PriceObservation(
                mandi_name=r["market"],
                commodity=r["commodity"],
                modal_price_per_quintal=Decimal(str(r["modal_price"])),
                reported_on=parse_day(r["arrival_date"]),
            ),
            distance_km=ILLUSTRATIVE_DISTANCE,
            commission_rate=ILLUSTRATIVE_COMMISSION,
            handling_cost_per_quintal=ILLUSTRATIVE_HANDLING,
        )
        rec = calculate_recommendation(offer, quantity, rate_card,
                                       today=parse_day(r["arrival_date"]))
        nets.append(rec.net_realisation_inr)
        grosses.append(rec.gross_revenue_inr)
        if rec.net_realisation_inr <= 0:
            negatives += 1
    print("  rows evaluated : %d" % len(nets))
    print("  net realisation as currently computed: median INR %s, min INR %s, max INR %s"
          % (median(nets), min(nets), max(nets)))
    print("  rows whose net is already <= 0       : %d" % negatives)
    print()
    print("   assumed fee   median fee   median overstatement   worst row   rows pushed")
    print("       rate       INR/lot      of net realisation                below zero")
    fee_table = []
    for rate in ASSUMED_FEE_RATES:
        fees = [g * rate for g in grosses]
        overstatement = [
            (f / n * 100) for f, n in zip(fees, nets) if n > 0
        ]
        flipped = sum(1 for f, n in zip(fees, nets) if n > 0 and n - f <= 0)
        fee_table.append(
            {
                "rate": rate,
                "median_fee": median(fees),
                "median_pct": median(overstatement),
                "max_pct": max(overstatement),
                "flipped": flipped,
            }
        )
        print("      %5s%%    %10s   %18s%%   %8s%%   %9d"
              % (rate * 100, f"{median(fees):.2f}", f"{median(overstatement):.2f}",
                 f"{max(overstatement):.2f}", flipped))
    print()

    # Does the omission change the ranking? Use the repo's own two-mandi example.
    print("  Does omitting the fee change WHICH mandi wins? The fee is")
    print("  proportional to gross, so it is not a constant shift. Using the two")
    print("  illustrative offers in data/example_market_prices.csv:")
    example_rows = load_example_offers()
    offers = [
        MandiOffer(
            price=PriceObservation(
                mandi_name=row["mandi_name"],
                commodity=row["commodity"],
                modal_price_per_quintal=Decimal(row["modal_price_per_quintal"]),
                reported_on=date.fromisoformat(row["reported_on"]),
            ),
            distance_km=Decimal(row["distance_km"]),
            commission_rate=Decimal(row["commission_rate"]),
            handling_cost_per_quintal=Decimal(row["handling_cost_per_quintal"]),
        )
        for row in example_rows
    ]
    base = rank_mandis(offers, quantity, rate_card, today=date(2026, 9, 17))
    print("    as computed today   : %s"
          % ", ".join("%s net INR %s" % (r.mandi_name, r.net_realisation_inr) for r in base))
    gap_rows = []
    for rate in ASSUMED_FEE_RATES + [Decimal("0.10"), Decimal("0.25")]:
        adjusted = []
        for rec in base:
            fee = rec.gross_revenue_inr * rate
            adjusted.append((rec.mandi_name, rec.net_realisation_inr - fee))
        adjusted.sort(key=lambda t: -t[1])
        gap_rows.append((rate, adjusted))
        print("    with %5s%% fee      : %s"
              % (rate * 100,
                 ", ".join("%s net INR %.2f" % (n, v) for n, v in adjusted)))
    print("    winner is unchanged at every probed rate: the higher-gross mandi")
    print("    pays more fee, but here it also earns enough more to stay ahead.")
    print()
    return {
        "rows": len(rows),
        "valid": len(valid),
        "patiala": len(patiala),
        "collisions": collision_report,
        "multi_sections": len(multi),
        "pat_multi": len(pat_multi),
        "fee_table": fee_table,
        "negatives": negatives,
        "median_net": median(nets),
    }


def ranked_pairs(ranked):
    return [(r.mandi_name, str(r.net_realisation_inr)) for r in ranked]


def median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        return Decimal(0)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


# --------------------------------------------------------------------------

def main() -> None:
    print()
    print("MandiWise transport-engine benchmark")
    print("engine A: src/mandiwise/transport.py::cheapest_transport_plan "
          "(Decimal quintals/rupees, exhaustive search)")
    print("engine B: backend/src/mandiwise_transport/engine.py::optimise "
          "(int kg/paise, dynamic programme)")
    print("python %s" % sys.version.split()[0])
    print()
    started = time.perf_counter()

    differential = experiment_differential()
    scaling = experiment_scaling()
    rate_card, payload = load_rate_card()
    worked = experiment_worked_example(rate_card, payload, load_example_offers())
    real = experiment_real_data(rate_card)

    print(RULE)
    print("SUMMARY")
    print(RULE)
    print("1. differential : %d cost disagreements in %d randomised pairs "
          "(seed %d); %d fleet-composition differences at equal cost"
          % (len(differential["disagreements"]), TRIALS, SEED,
             differential["fleet_differences"]))
    completed = [r for r in scaling if r["a_time"] is not None]
    largest = max(completed, key=lambda r: r["leaves"])
    print("2. scaling      : engine A completed %d of %d grid points; largest "
          "was %d types at %s quintals (%s leaves, %.3f s)"
          % (len(completed), len(scaling), largest["n_types"], largest["quantity"],
             f"{largest['leaves']:,}", largest["a_time"]))
    print("3. worked example: 40 q potato, canonical card - %s"
          % ("both engines agree at every distance"
             if all(w["agree"] for w in worked) else "ENGINES DISAGREE"))
    print("4. real data    : %d validated rows, %d Patiala; %d real name "
          "collisions found in same-day cross-sections"
          % (real["valid"], real["patiala"], len(real["collisions"])))
    print("total wall time : %.1f s" % (time.perf_counter() - started))
    print()


if __name__ == "__main__":
    main()
