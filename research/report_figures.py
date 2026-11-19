#!/usr/bin/env python3
"""Generate the data behind the report's charts, from committed data only.

    python research/report_figures.py

Writes small CSVs to report/data/ that the LaTeX figures plot with pgfplots,
and prints every number the figure captions quote. Nothing here is estimated:

- Only files tracked by git under data/ are read, so an uncommitted local pull
  can never change a published figure.
- The dispersion grouping is the one in mandi_pull.analyse(): same date,
  commodity, variety and grade, at least 3 markets, Rs 50/quintal floor. The
  script asserts it reproduces research/findings.md (2,821 groups, 73.1%
  median) before writing anything.
- The transport curve calls the canonical engine
  (backend/src/mandiwise_transport/engine.py) on data/vehicle_rates.json,
  the repo's single PLACEHOLDER rate card.

Historical rows come from CEDA Agri Market Data (CEDA-AMD), Centre for
Economic Data & Analysis, Ashoka University; figures derived from them must
carry that attribution and CEDA's logo (docs/DECISIONS.md, 2026-09-04).
"""

import csv
import json
import subprocess
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report" / "data"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend" / "src"))

from mandi_pull import PRICE_FLOOR, _parse_date  # noqa: E402
from mandiwise_transport.engine import (  # noqa: E402
    Vehicle,
    kg,
    optimise,
    trip_cost_paise,
)

LIQUIDITY_START, LIQUIDITY_END = date(2025, 10, 1), date(2025, 10, 30)
DISTANCE_KM = Decimal(60)


def tracked_rows():
    """Rows from tracked price snapshots, de-duplicated as mandi_pull does."""
    names = subprocess.run(
        ["git", "ls-files", "data/*.json"], cwd=ROOT, capture_output=True,
        text=True, check=True,
    ).stdout.split()
    rows = []
    for name in sorted(names):
        payload = json.loads((ROOT / name).read_text(encoding="utf-8"))
        if isinstance(payload, list) and all(isinstance(r, dict) for r in payload):
            rows += payload
    seen, unique = set(), []
    for r in rows:
        key = (r.get("arrival_date"), r.get("market"), r.get("commodity"),
               r.get("variety"), r.get("grade"))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def modal(r):
    try:
        value = float(r["modal_price"])
    except (KeyError, TypeError, ValueError):
        return None
    return value if value >= PRICE_FLOOR else None


def dispersion_groups(rows):
    groups = defaultdict(dict)
    for r in rows:
        price = modal(r)
        if price is None:
            continue
        key = (r.get("arrival_date"), r.get("commodity"), r.get("variety"),
               r.get("grade"))
        groups[key][r.get("market")] = price
    out = []
    for (day, commodity, variety, grade), markets in groups.items():
        if len(markets) >= 3:
            lo, hi = min(markets.values()), max(markets.values())
            out.append({"commodity": commodity, "historical": grade == "",
                        "dispersion": (hi - lo) / lo})
    return out


def write(name, header, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / name, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def main():
    rows = tracked_rows()
    groups = dispersion_groups(rows)
    values = sorted(g["dispersion"] for g in groups)
    n = len(values)
    med = median(values) * 100
    assert n == 2821 and round(med, 1) == 73.1, (n, med)
    print(f"rows {len(rows)}; groups {n}; P25 {values[n // 4] * 100:.1f}% "
          f"median {med:.1f}% P75 {values[3 * n // 4] * 100:.1f}%")

    # Fig: distribution of same-day dispersion, 10-point bins, overflow last.
    bins = [0] * 21
    for v in values:
        bins[min(int(v * 100 // 10), 20)] += 1
    write("dispersion_hist.csv", ["lo", "count"],
          [(i * 10, c) for i, c in enumerate(bins)])
    print(f"share below 10%: {sum(v < 0.10 for v in values) / n * 100:.1f}%; "
          f"at or above 200%: {bins[20]} groups")

    # Fig: median dispersion by crop, historical (CEDA) groups only.
    by_crop = defaultdict(list)
    for g in groups:
        if g["historical"]:
            by_crop[g["commodity"]].append(g["dispersion"])
    crop_rows = sorted(((c, c.split(" (")[0], round(median(v) * 100, 1), len(v))
                        for c, v in by_crop.items()), key=lambda x: -x[2])
    write("dispersion_by_crop.csv", ["crop", "label", "median", "groups"], crop_rows)
    print("by crop:", crop_rows)

    # Fig: potato, weekly cheapest vs dearest Patiala mandi (historical).
    daily = defaultdict(dict)
    for r in rows:
        if r.get("source") == "ceda" and r.get("commodity") == "Potato":
            price, day = modal(r), _parse_date(r.get("arrival_date"))
            if price is not None and day:
                daily[day][r.get("market")] = price
    weekly = defaultdict(lambda: ([], []))
    for day, markets in daily.items():
        if len(markets) >= 3:
            iso = day.isocalendar()
            weekly[(iso[0], iso[1])][0].append(min(markets.values()))
            weekly[(iso[0], iso[1])][1].append(max(markets.values()))
    band = []
    for (year, week), (lows, highs) in sorted(weekly.items()):
        monday = date.fromisocalendar(year, week, 1)
        x = monday.year + (monday.timetuple().tm_yday - 1) / 365.25
        band.append((round(x, 4), median(lows), median(highs)))
    write("potato_band.csv", ["x", "low", "high"], band)
    gaps = [h / lo - 1 for _, lo, h in band]
    print(f"potato weeks {len(band)}; median weekly gap {median(gaps) * 100:.1f}%; "
          f"max weekly gap {max(gaps) * 100:.1f}%")

    # Fig: liquidity, reporting days per mandi x crop in the 30-day window.
    days = defaultdict(set)
    for r in rows:
        day = _parse_date(r.get("arrival_date"))
        if r.get("source") == "ceda" and day and LIQUIDITY_START <= day <= LIQUIDITY_END:
            days[(r.get("market"), r.get("commodity"))].add(day)
    counts = sorted(len(v) for v in days.values())
    assert len(counts) == 45 and median(counts) == 21, (len(counts), median(counts))
    markets = sorted({m for m, _ in days})
    crops = sorted({c for _, c in days})
    write("liquidity.csv", ["mandi", "crop", "x", "y", "days"],
          [(m, c, crops.index(c), markets.index(m), len(days.get((m, c), ())))
           for m in markets for c in crops])
    print(f"liquidity pairs {len(counts)}; median {median(counts)}; "
          f"mandis {markets}; crops {crops}")

    # Fig: transport cost per quintal on the placeholder card, at 60 km.
    card = json.loads((ROOT / "data" / "vehicle_rates.json").read_text())
    fleet = [
        Vehicle(v["name"].lower(), kg(Decimal(str(v["capacity_quintals"]))),
                trip_cost_paise(Decimal(str(v["base_cost_inr"])),
                                Decimal(str(v["per_km_cost_inr"])), DISTANCE_KM))
        for v in card["vehicles"]
    ]
    tempo = [v for v in fleet if v.code == "tempo"]
    curve = []
    for q in range(1, 151):
        best = optimise(q * 100, fleet)["cost_paise"] / 100
        alone = optimise(q * 100, tempo)["cost_paise"] / 100
        curve.append((q, round(best / q, 2), round(alone / q, 2)))
    write("cost_per_quintal.csv", ["q", "optimal", "tempo_only"], curve)
    print(f"cost/q at 40 q {curve[39][1]} (total {curve[39][1] * 40:.0f}); "
          f"at 80 q {curve[79][1]} (total {curve[79][1] * 80:.0f})")


if __name__ == "__main__":
    main()
