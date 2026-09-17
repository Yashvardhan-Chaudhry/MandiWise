"""Validated value objects shared by the calculation modules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


Money = Decimal


def as_decimal(value: Decimal | int | float | str, field: str) -> Decimal:
    """Convert values through their string form so money is never calculated as float."""
    try:
        return Decimal(str(value))
    except Exception as exc:  # pragma: no cover - defensive conversion guard
        raise ValueError(f"{field} must be numeric") from exc


@dataclass(frozen=True)
class VehicleType:
    name: str
    capacity_quintals: Decimal
    base_cost_inr: Decimal
    per_km_cost_inr: Decimal

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("vehicle name is required")
        if as_decimal(self.capacity_quintals, "capacity_quintals") <= 0:
            raise ValueError("vehicle capacity must be greater than zero")
        if as_decimal(self.base_cost_inr, "base_cost_inr") < 0:
            raise ValueError("vehicle base cost cannot be negative")
        if as_decimal(self.per_km_cost_inr, "per_km_cost_inr") < 0:
            raise ValueError("vehicle per-km cost cannot be negative")

    def trip_cost(self, distance_km: Decimal | int | float | str) -> Decimal:
        distance = as_decimal(distance_km, "distance_km")
        if distance < 0:
            raise ValueError("distance cannot be negative")
        return as_decimal(self.base_cost_inr, "base_cost_inr") + (
            as_decimal(self.per_km_cost_inr, "per_km_cost_inr") * distance
        )


@dataclass(frozen=True)
class PriceObservation:
    mandi_name: str
    commodity: str
    modal_price_per_quintal: Decimal
    reported_on: date

    def __post_init__(self) -> None:
        if not self.mandi_name.strip() or not self.commodity.strip():
            raise ValueError("mandi name and commodity are required")
        if as_decimal(self.modal_price_per_quintal, "modal_price_per_quintal") <= 0:
            raise ValueError("modal price must be greater than zero")


@dataclass(frozen=True)
class MandiOffer:
    price: PriceObservation
    distance_km: Decimal
    commission_rate: Decimal
    handling_cost_per_quintal: Decimal

    def __post_init__(self) -> None:
        if as_decimal(self.distance_km, "distance_km") < 0:
            raise ValueError("distance cannot be negative")
        rate = as_decimal(self.commission_rate, "commission_rate")
        if not Decimal("0") <= rate <= Decimal("1"):
            raise ValueError("commission_rate must be between 0 and 1")
        if as_decimal(self.handling_cost_per_quintal, "handling_cost_per_quintal") < 0:
            raise ValueError("handling cost cannot be negative")


@dataclass(frozen=True)
class TransportPlan:
    total_cost_inr: Decimal
    total_capacity_quintals: Decimal
    vehicles: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class Recommendation:
    mandi_name: str
    commodity: str
    reported_on: date
    is_stale: bool
    modal_price_per_quintal: Decimal
    quantity_quintals: Decimal
    gross_revenue_inr: Decimal
    commission_inr: Decimal
    handling_inr: Decimal
    transport_inr: Decimal
    net_realisation_inr: Decimal
    transport_plan: TransportPlan
