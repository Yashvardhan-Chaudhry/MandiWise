"""Pure calculations. No database, network, or framework imports.

Quantities use integer kg, distances metres and money integer paise internally.
Vehicle costs are rounded once, per vehicle, with commercial half-up rounding.
The optimiser is exact for quantities specified to 0.01 quintal (one kg).
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

MAX_KG = 100_000


class TransportError(ValueError):
    pass


def kg(quintals: Decimal) -> int:
    value = quintals * 100
    if not value.is_finite() or value != value.to_integral_value() or not 0 < value <= MAX_KG:
        raise TransportError("Quantity must be 0.01 to 1000 quintals in whole kilograms")
    return int(value)


def paise(rupees: Decimal) -> int:
    if not rupees.is_finite() or rupees < 0:
        raise TransportError("Cost must be a finite non-negative value")
    return int((rupees * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def rupees(value: int) -> str:
    return format(Decimal(value) / 100, ".2f")


def trip_cost_paise(base_inr: Decimal, per_km_inr: Decimal, distance_km: Decimal) -> int:
    """One vehicle's trip price: base + per-km x distance, rounded once, half-up.

    This is the only place the trip-cost formula lives; quotes, the calculator and
    the ranking all call it.
    """
    if not distance_km.is_finite() or distance_km < 0:
        raise TransportError("Distance must be a finite non-negative value")
    if not base_inr.is_finite() or not per_km_inr.is_finite() or base_inr < 0 or per_km_inr < 0:
        raise TransportError("Vehicle rates must be finite non-negative values")
    return paise(base_inr + per_km_inr * distance_km)


def _half_up(numerator: int, denominator: int) -> int:
    """Integer division rounded half-up, for non-negative numerators."""
    return (2 * numerator + denominator) // (2 * denominator)


@dataclass(frozen=True)
class Vehicle:
    code: str
    capacity_kg: int
    cost_paise: int


def optimise(quantity_kg: int, vehicles: list[Vehicle]) -> dict:
    """Unbounded integer covering DP: minimum cost, then count, then spare capacity.

    This models rate-card options, NOT live fleet availability. Requests are bounded
    to 100 tonnes and 12 classes. Equal solutions break ties by sorted vehicle code.
    """
    if type(quantity_kg) is not int or not 0 < quantity_kg <= MAX_KG:
        raise TransportError("Quantity exceeds the supported 1..100000 kg range")
    if not 1 <= len(vehicles) <= 12 or len({v.code for v in vehicles}) != len(vehicles):
        raise TransportError("Provide 1..12 uniquely named vehicle classes")
    options = sorted(vehicles, key=lambda v: v.code)
    if any(
        type(v.capacity_kg) is not int
        or not 0 < v.capacity_kg <= MAX_KG
        or type(v.cost_paise) is not int
        or v.cost_paise <= 0
        for v in options
    ):
        raise TransportError("Vehicle capacity and trip price must be positive integers")
    scores = [(0, 0, 0)] * (quantity_kg + 1)
    choice = [0] * (quantity_kg + 1)
    for remaining in range(1, quantity_kg + 1):
        best = None
        for i, vehicle in enumerate(options):
            prior = scores[max(0, remaining - vehicle.capacity_kg)]
            candidate = (
                prior[0] + vehicle.cost_paise,
                prior[1] + 1,
                prior[2] + vehicle.capacity_kg,
            )
            if best is None or candidate < best:
                best, choice[remaining] = candidate, i
        scores[remaining] = best
    counts = [0] * len(options)
    remaining = quantity_kg
    while remaining > 0:
        i = choice[remaining]
        counts[i] += 1
        remaining -= options[i].capacity_kg
    cost, count, capacity = scores[quantity_kg]
    return {
        "quantity_kg": quantity_kg,
        "capacity_kg": capacity,
        "unused_capacity_kg": capacity - quantity_kg,
        "vehicle_count": count,
        "cost_paise": cost,
        "cost_inr": rupees(cost),
        "cost_per_quintal_inr": format(Decimal(cost) / quantity_kg, ".2f"),
        "vehicles": [
            {
                "code": v.code,
                "count": n,
                "capacity_kg": v.capacity_kg,
                "unit_cost_inr": rupees(v.cost_paise),
            }
            for v, n in zip(options, counts)
            if n
        ],
    }


def allocate_cost(total_paise: int, quantities: dict[str, int]) -> dict[str, int]:
    """Largest remainder apportionment conserves every paisa; ID breaks ties."""
    if total_paise < 0 or not quantities or any(q <= 0 for q in quantities.values()):
        raise TransportError("Non-negative cost and positive participant quantities required")
    total_kg = sum(quantities.values())
    shares = {key: total_paise * q // total_kg for key, q in quantities.items()}
    order = sorted(quantities, key=lambda key: (-(total_paise * quantities[key] % total_kg), key))
    for key in order[: total_paise - sum(shares.values())]:
        shares[key] += 1
    return shares


def pool_quote(quantities: dict[str, int], vehicles: list[Vehicle]) -> dict:
    if not 1 <= len(quantities) <= 50 or any(q <= 0 for q in quantities.values()):
        raise TransportError("Provide 1..50 positive participant quantities")
    plan = optimise(sum(quantities.values()), vehicles)
    shares = allocate_cost(plan["cost_paise"], quantities)
    members = []
    individual_total = 0
    for key, quantity in sorted(quantities.items()):
        alone = optimise(quantity, vehicles)
        individual = alone["cost_paise"]
        individual_total += individual
        members.append(
            {
                "participant_id": key,
                "quantity_kg": quantity,
                "share_inr": rupees(shares[key]),
                "individual_cost_inr": rupees(individual),
                "individual_vehicles": alone["vehicles"],
                "savings_inr": rupees(individual - shares[key]),
                "benefits_from_pooling": individual >= shares[key],
            }
        )
    plan["participants"] = members
    plan["individual_total_inr"] = rupees(individual_total)
    plan["total_savings_inr"] = format(sum(Decimal(m["savings_inr"]) for m in members), ".2f")
    plan["all_participants_benefit"] = all(m["benefits_from_pooling"] for m in members)
    return plan


BASIS_POINTS = 10_000


def _deductions(price_paise_per_q, quantity_kg, commission_bp, market_fee_bp, handling, transport):
    # A quintal is 100 kg, so value = price per quintal x kg / 100. Each component is
    # rounded to the paisa on its own and net is taken from the rounded components,
    # so a printed breakdown always adds up to the printed net.
    gross = _half_up(price_paise_per_q * quantity_kg, 100)
    commission = _half_up(gross * commission_bp, BASIS_POINTS)
    market_fee = _half_up(gross * market_fee_bp, BASIS_POINTS)
    net = gross - commission - market_fee - handling - transport
    return gross, commission, market_fee, net


def net_realisation(
    *,
    quantity_kg: int,
    modal_paise_per_quintal: int,
    min_paise_per_quintal: int,
    max_paise_per_quintal: int,
    commission_bp: int,
    market_fee_bp: int,
    handling_paise_per_quintal: int,
    transport_paise: int,
) -> dict:
    """Money that reaches the farmer at one mandi (ARCHITECTURE.md section 3.3).

    net = gross - commission - market_fee - handling - transport, in integer paise.
    Rates are basis points of gross (400 bp = 4%). The modal price gives the headline
    figure; the reported min and max prices give a range, because the modal price is
    a typical outcome, not a guarantee. Handling and transport do not depend on the
    price, so they are identical across the range. Net may be negative.
    """
    for name, value in (
        ("quantity_kg", quantity_kg),
        ("modal_paise_per_quintal", modal_paise_per_quintal),
        ("min_paise_per_quintal", min_paise_per_quintal),
        ("max_paise_per_quintal", max_paise_per_quintal),
        ("commission_bp", commission_bp),
        ("market_fee_bp", market_fee_bp),
        ("handling_paise_per_quintal", handling_paise_per_quintal),
        ("transport_paise", transport_paise),
    ):
        if type(value) is not int:
            raise TransportError(f"{name} must be an integer")
    if not 0 < quantity_kg <= MAX_KG:
        raise TransportError("Quantity exceeds the supported 1..100000 kg range")
    if not 0 < min_paise_per_quintal <= modal_paise_per_quintal <= max_paise_per_quintal:
        raise TransportError("Prices must be positive with min <= modal <= max")
    if not 0 <= commission_bp <= BASIS_POINTS or not 0 <= market_fee_bp <= BASIS_POINTS:
        raise TransportError("Commission and market fee must be 0..10000 basis points")
    if handling_paise_per_quintal < 0 or transport_paise < 0:
        raise TransportError("Handling and transport must be non-negative")
    handling = _half_up(handling_paise_per_quintal * quantity_kg, 100)
    fixed = (quantity_kg, commission_bp, market_fee_bp, handling, transport_paise)
    gross, commission, market_fee, net = _deductions(modal_paise_per_quintal, *fixed)
    net_min = _deductions(min_paise_per_quintal, *fixed)[3]
    net_max = _deductions(max_paise_per_quintal, *fixed)[3]
    return {
        "gross_paise": gross,
        "commission_paise": commission,
        "market_fee_paise": market_fee,
        "handling_paise": handling,
        "transport_paise": transport_paise,
        "net_paise": net,
        "net_min_paise": net_min,
        "net_max_paise": net_max,
    }


def rank_offers(offers: list[dict]) -> list[dict]:
    """Order by net realisation, highest first; nearer mandi, then name, break ties.

    Each offer needs net_paise, distance_m and market. Returns new dicts with rank.
    """
    ordered = sorted(offers, key=lambda o: (-o["net_paise"], o["distance_m"], o["market"]))
    return [{**offer, "rank": i + 1} for i, offer in enumerate(ordered)]
