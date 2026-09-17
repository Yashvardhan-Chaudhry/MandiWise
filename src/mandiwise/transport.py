"""Transport calculation using whole vehicle units, never fractional vehicles."""

from __future__ import annotations

from decimal import Decimal
from math import ceil

from .models import TransportPlan, VehicleType, as_decimal


def cheapest_transport_plan(
    quantity_quintals: Decimal | int | float | str,
    distance_km: Decimal | int | float | str,
    vehicle_types: list[VehicleType] | tuple[VehicleType, ...],
) -> TransportPlan:
    """Choose the least-cost vehicle combination with enough whole-unit capacity.

    This bounded search is appropriate for a single farmer/pool request and is
    deliberately explicit, making its result straightforward to test and explain.
    """
    quantity = as_decimal(quantity_quintals, "quantity_quintals")
    if quantity <= 0:
        raise ValueError("quantity must be greater than zero")
    if not vehicle_types:
        raise ValueError("at least one vehicle type is required")

    min_capacity = min(as_decimal(v.capacity_quintals, "capacity") for v in vehicle_types)
    # A feasible answer can always be built from the smallest vehicle.  This is
    # therefore a safe per-type bound even when a large vehicle is expensive.
    vehicle_limit = ceil(float(quantity / min_capacity))
    best: TransportPlan | None = None

    def search(index: int, chosen: list[int]) -> None:
        nonlocal best
        if index == len(vehicle_types):
            capacity = sum(
                as_decimal(vehicle_types[i].capacity_quintals, "capacity") * chosen[i]
                for i in range(len(vehicle_types))
            )
            if capacity < quantity:
                return
            cost = sum(
                vehicle_types[i].trip_cost(distance_km) * chosen[i]
                for i in range(len(vehicle_types))
            )
            candidate = TransportPlan(
                total_cost_inr=cost,
                total_capacity_quintals=capacity,
                vehicles=tuple(
                    (vehicle_types[i].name, chosen[i])
                    for i in range(len(vehicle_types))
                    if chosen[i]
                ),
            )
            if best is None or (candidate.total_cost_inr, candidate.total_capacity_quintals) < (
                best.total_cost_inr,
                best.total_capacity_quintals,
            ):
                best = candidate
            return
        for count in range(vehicle_limit + 1):
            chosen.append(count)
            search(index + 1, chosen)
            chosen.pop()

    search(0, [])
    assert best is not None  # Every positive quantity is feasible with any vehicle type.
    return best
