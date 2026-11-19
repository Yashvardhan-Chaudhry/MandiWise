"""Read-only price and rate inputs for the mandi ranking, plus its orchestration.

Prices come from the committed AGMARKNET snapshots (``data/punjab_*.json``), read
once per process. The government API is never called in the request path. This
module is the repository seam: when scheduled ingestion writes a ``price_record``
table, only ``PriceBook`` changes. All arithmetic is delegated to ``engine``.

Rates come from two files that are labelled PLACEHOLDER - NOT SOURCED:
``data/market_rates.json`` (commission, market fee, handling) and
``data/vehicle_rates.json`` (transport). Every response says so.
"""

import json
import threading
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .engine import (
    TransportError,
    Vehicle,
    kg,
    net_realisation,
    optimise,
    paise,
    rank_offers,
    rupees,
    trip_cost_paise,
)

# docs/DECISIONS.md 2026-09-04: rows under Rs 50/quintal are placeholder entries in
# the feed. They are rejected and counted, never corrected.
PRICE_FLOOR_PAISE = 5_000
# docs/DECISIONS.md 2026-11-19: a price is stale when it is MORE than this many days
# old (so 3 days or older). Stale prices are shown, flagged, never substituted.
STALE_AFTER_DAYS = 2
SNAPSHOT_GLOB = "punjab_*.json"


class PricingUnavailable(Exception):
    pass


@dataclass(frozen=True)
class Observation:
    state: str
    district: str
    market: str
    commodity: str
    variety: str
    grade: str
    price_date: date
    min_paise: int
    modal_paise: int
    max_paise: int


def _money(value) -> int:
    return paise(Decimal(str(value)))


def _parse(row: dict) -> Observation | None:
    try:
        observation = Observation(
            state=str(row["state"]).strip(),
            district=str(row["district"]).strip(),
            market=str(row["market"]).strip(),
            commodity=str(row["commodity"]).strip(),
            variety=str(row.get("variety") or "").strip(),
            grade=str(row.get("grade") or "").strip(),
            price_date=datetime.strptime(str(row["arrival_date"]), "%d/%m/%Y").date(),
            min_paise=_money(row["min_price"]),
            modal_paise=_money(row["modal_price"]),
            max_paise=_money(row["max_price"]),
        )
    except (KeyError, TypeError, ValueError, InvalidOperation, TransportError):
        return None
    return observation


class PriceBook:
    """Latest valid observation per (state, district, market, commodity, variety, grade)."""

    def __init__(self, data_dir: Path):
        self.files: list[str] = []
        self.rejected = {"unparseable": 0, "below_floor": 0, "outside_min_max": 0}
        latest: dict[tuple, Observation] = {}
        for path in sorted(Path(data_dir).glob(SNAPSHOT_GLOB)):
            try:
                rows = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(rows, list):
                continue
            self.files.append(path.name)
            for row in rows:
                obs = _parse(row) if isinstance(row, dict) else None
                if obs is None:
                    self.rejected["unparseable"] += 1
                elif obs.modal_paise < PRICE_FLOOR_PAISE:
                    self.rejected["below_floor"] += 1
                elif not obs.min_paise <= obs.modal_paise <= obs.max_paise:
                    self.rejected["outside_min_max"] += 1
                else:
                    key = (
                        obs.state,
                        obs.district,
                        obs.market,
                        obs.commodity,
                        obs.variety,
                        obs.grade,
                    )
                    if key not in latest or latest[key].price_date < obs.price_date:
                        latest[key] = obs
        if not self.files:
            raise PricingUnavailable(f"No price snapshots matching {SNAPSHOT_GLOB} in {data_dir}")
        self.observations = sorted(
            latest.values(), key=lambda o: (o.commodity, o.market, o.variety, o.grade)
        )

    @property
    def source(self) -> str:
        return "AGMARKNET daily prices via data.gov.in, committed snapshots: " + ", ".join(
            self.files
        )

    def commodities(self) -> list[str]:
        return sorted({o.commodity for o in self.observations}, key=str.casefold)

    def for_commodity(self, commodity: str) -> list[Observation]:
        wanted = commodity.strip().casefold()
        return [o for o in self.observations if o.commodity.casefold() == wanted]


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PricingUnavailable(f"Cannot read {path.name}") from exc


class Inputs:
    """Everything the ranking reads, loaded once and shared across requests."""

    def __init__(self, data_dir: Path):
        self.prices = PriceBook(data_dir)
        market = _read_json(Path(data_dir) / "market_rates.json")
        default = market["default"]
        self.market_rates = {
            "source": market["source"],
            "effective_from": market["effective_from"],
            "is_placeholder": bool(market.get("is_placeholder", True)),
            "commission_bp": int(default["commission_bp"]),
            "market_fee_bp": int(default["market_fee_bp"]),
            "handling_paise_per_quintal": _money(default["handling_per_quintal_inr"]),
        }
        card = _read_json(Path(data_dir) / "vehicle_rates.json")
        self.vehicle_card = {
            "source": card["vehicles"][0]["source"],
            "effective_from": card["effective_from"],
            "vehicles": [
                {
                    "code": v["name"].strip().lower(),
                    "name": v["name"],
                    "capacity_quintals": Decimal(str(v["capacity_quintals"])),
                    "base_cost_inr": Decimal(str(v["base_cost_inr"])),
                    "per_km_inr": Decimal(str(v["per_km_cost_inr"])),
                }
                for v in card["vehicles"]
            ],
        }


_lock = threading.Lock()


def inputs_for(app) -> Inputs:
    with _lock:
        if getattr(app.state, "pricing_inputs", None) is None:
            app.state.pricing_inputs = Inputs(app.state.data_dir)
        return app.state.pricing_inputs


def _age(obs: Observation, today: date) -> dict:
    age = (today - obs.price_date).days
    return {
        "price_date": obs.price_date.isoformat(),
        "age_days": age,
        "is_stale": age > STALE_AFTER_DAYS,
    }


def _price_view(obs: Observation, today: date) -> dict:
    return {
        "market": obs.market,
        "district": obs.district,
        "state": obs.state,
        "commodity": obs.commodity,
        "variety": obs.variety,
        "grade": obs.grade,
        **_age(obs, today),
        "min_price": rupees(obs.min_paise),
        "modal_price": rupees(obs.modal_paise),
        "max_price": rupees(obs.max_paise),
    }


def _snapshot_warnings(views: list[dict]) -> list[str]:
    stale = sum(1 for v in views if v["is_stale"])
    if not stale:
        return []
    return [
        f"{stale} of {len(views)} prices are more than {STALE_AFTER_DAYS} days old. "
        "They are shown with their date and are not current."
    ]


def commodities(data: Inputs) -> dict:
    return {
        "commodities": data.prices.commodities(),
        "source": data.prices.source,
        "warnings": [],
    }


def markets(data: Inputs, commodity: str, today: date) -> dict:
    views = [_price_view(o, today) for o in data.prices.for_commodity(commodity)]
    return {
        "as_of": today.isoformat(),
        "stale_after_days": STALE_AFTER_DAYS,
        "source": data.prices.source,
        "rejected_rows": data.prices.rejected,
        "markets": views,
        "warnings": _snapshot_warnings(views),
    }


def rank(data: Inputs, commodity: str, quantity_quintals: Decimal, candidates, today: date):
    rates, card = data.market_rates, data.vehicle_card
    quantity_kg = kg(quantity_quintals)
    available = data.prices.for_commodity(commodity)
    offers, unmatched, seen = [], [], set()
    for candidate in candidates:
        market = candidate.market.strip().casefold()
        district = (candidate.district or "").strip().casefold()
        if (market, district) in seen:
            continue
        seen.add((market, district))
        matches = [
            o
            for o in available
            if o.market.casefold() == market and (not district or o.district.casefold() == district)
        ]
        if not matches:
            unmatched.append(
                {
                    "market": candidate.market,
                    "reason": f"No valid {commodity} price for this market in the snapshots",
                }
            )
            continue
        vehicles = [
            Vehicle(
                v["code"],
                kg(v["capacity_quintals"]),
                trip_cost_paise(v["base_cost_inr"], v["per_km_inr"], candidate.distance_km),
            )
            for v in card["vehicles"]
        ]
        plan = optimise(quantity_kg, vehicles)
        names = {v["code"]: v["name"] for v in card["vehicles"]}
        for obs in matches:
            money = net_realisation(
                quantity_kg=quantity_kg,
                modal_paise_per_quintal=obs.modal_paise,
                min_paise_per_quintal=obs.min_paise,
                max_paise_per_quintal=obs.max_paise,
                commission_bp=rates["commission_bp"],
                market_fee_bp=rates["market_fee_bp"],
                handling_paise_per_quintal=rates["handling_paise_per_quintal"],
                transport_paise=plan["cost_paise"],
            )
            offers.append(
                {
                    **_price_view(obs, today),
                    "distance_km": str(candidate.distance_km),
                    "distance_m": int(candidate.distance_km * 1000),
                    **money,
                    "vehicles": [
                        {"code": v["code"], "name": names[v["code"]], "count": v["count"]}
                        for v in plan["vehicles"]
                    ],
                }
            )
    results = []
    for offer in rank_offers(offers):
        offer.pop("distance_m")
        for key in [k for k in offer if k.endswith("_paise")]:
            offer[key.removesuffix("_paise")] = rupees(offer.pop(key))
        results.append(offer)

    warnings = []
    if rates["is_placeholder"]:
        warnings.append(
            "PLACEHOLDER market rates: commission, market fee and handling are not sourced. "
            "Do not quote these figures to a farmer."
        )
    if rates["market_fee_bp"] == 0:
        warnings.append(
            "Market fee (cess) is not yet sourced and is set to 0, so every net figure "
            "is overstated by the fee."
        )
    warnings.append(
        "PLACEHOLDER transport rates: the vehicle rate card is not sourced; "
        "vehicle availability is assumed, nothing is booked."
    )
    warnings.append("Distances are entered by the user, not taken from a route matrix.")
    warnings.extend(_snapshot_warnings(results))
    return {
        "as_of": today.isoformat(),
        "is_demo": True,
        "commodity": commodity,
        "quantity_quintals": str(quantity_quintals),
        "price_source": data.prices.source,
        "stale_after_days": STALE_AFTER_DAYS,
        "rates": {
            "source": rates["source"],
            "effective_from": rates["effective_from"],
            "commission_bp": rates["commission_bp"],
            "market_fee_bp": rates["market_fee_bp"],
            "handling_per_quintal": rupees(rates["handling_paise_per_quintal"]),
        },
        "vehicle_rates": {"source": card["source"], "effective_from": card["effective_from"]},
        "warnings": warnings,
        "results": results,
        "unmatched": unmatched,
    }
