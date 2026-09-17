"""Transparent net-realisation calculation and mandi ranking."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from .models import MandiOffer, Recommendation, VehicleType, as_decimal
from .transport import cheapest_transport_plan


RUPEE = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(RUPEE, rounding=ROUND_HALF_UP)


def calculate_recommendation(
    offer: MandiOffer,
    quantity_quintals: Decimal | int | float | str,
    vehicle_types: list[VehicleType] | tuple[VehicleType, ...],
    *,
    today: date | None = None,
    stale_after_days: int = 2,
) -> Recommendation:
    """Calculate the explained return for one mandi; this performs no I/O."""
    quantity = as_decimal(quantity_quintals, "quantity_quintals")
    if quantity <= 0:
        raise ValueError("quantity must be greater than zero")
    if stale_after_days < 0:
        raise ValueError("stale_after_days cannot be negative")
    transport_plan = cheapest_transport_plan(quantity, offer.distance_km, vehicle_types)
    gross = as_decimal(offer.price.modal_price_per_quintal, "modal_price") * quantity
    commission = gross * as_decimal(offer.commission_rate, "commission_rate")
    handling = as_decimal(offer.handling_cost_per_quintal, "handling") * quantity
    reference_day = today or date.today()
    return Recommendation(
        mandi_name=offer.price.mandi_name,
        commodity=offer.price.commodity,
        reported_on=offer.price.reported_on,
        is_stale=offer.price.reported_on < reference_day - timedelta(days=stale_after_days),
        modal_price_per_quintal=money(as_decimal(offer.price.modal_price_per_quintal, "modal_price")),
        quantity_quintals=quantity,
        gross_revenue_inr=money(gross),
        commission_inr=money(commission),
        handling_inr=money(handling),
        transport_inr=money(transport_plan.total_cost_inr),
        net_realisation_inr=money(gross - commission - handling - transport_plan.total_cost_inr),
        transport_plan=transport_plan,
    )


def rank_mandis(
    offers: list[MandiOffer] | tuple[MandiOffer, ...],
    quantity_quintals: Decimal | int | float | str,
    vehicle_types: list[VehicleType] | tuple[VehicleType, ...],
    **kwargs: object,
) -> list[Recommendation]:
    """Return recommendations highest net amount first; ties favour the nearer mandi."""
    results = [
        calculate_recommendation(offer, quantity_quintals, vehicle_types, **kwargs)
        for offer in offers
    ]
    distance_by_mandi = {offer.price.mandi_name: offer.distance_km for offer in offers}
    return sorted(
        results,
        key=lambda item: (-item.net_realisation_inr, distance_by_mandi[item.mandi_name], item.mandi_name),
    )
