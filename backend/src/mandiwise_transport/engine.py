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
    for key, quantity in sorted(quantities.items()):
        individual = optimise(quantity, vehicles)["cost_paise"]
        members.append(
            {
                "participant_id": key,
                "quantity_kg": quantity,
                "share_inr": rupees(shares[key]),
                "individual_cost_inr": rupees(individual),
                "savings_inr": rupees(individual - shares[key]),
                "benefits_from_pooling": individual >= shares[key],
            }
        )
    plan["participants"] = members
    plan["total_savings_inr"] = format(sum(Decimal(m["savings_inr"]) for m in members), ".2f")
    plan["all_participants_benefit"] = all(m["benefits_from_pooling"] for m in members)
    return plan
