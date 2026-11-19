"""net_realisation: ARCHITECTURE.md section 3.3, rebuilt in the canonical engine.

The acceptance test is Dhrity's hand-verified worked example from
tests/test_recommendation.py (40 q potato, 4% commission, Rs 30/q handling, a
base-0 Rs 75/km tempo card), which must reproduce exactly in integer paise.
"""

from decimal import Decimal

import pytest

from mandiwise_transport.engine import (
    TransportError,
    Vehicle,
    kg,
    net_realisation,
    optimise,
    rank_offers,
    trip_cost_paise,
)


def worked(price, distance_km, fee_bp=0, low=None, high=None):
    # The worked example's own card: Tempo, 30 q, base 0, Rs 75/km.
    tempo = Vehicle("tempo", kg(Decimal(30)), trip_cost_paise(Decimal(0), Decimal(75), distance_km))
    transport = optimise(kg(Decimal(40)), [tempo])["cost_paise"]
    return net_realisation(
        quantity_kg=kg(Decimal(40)),
        modal_paise_per_quintal=price * 100,
        min_paise_per_quintal=(low or price) * 100,
        max_paise_per_quintal=(high or price) * 100,
        commission_bp=400,
        market_fee_bp=fee_bp,
        handling_paise_per_quintal=3000,
        transport_paise=transport,
    )


def test_worked_example_is_the_acceptance_test():
    local, distant = worked(1200, Decimal(20)), worked(1380, Decimal(60))
    assert (local["gross_paise"], local["commission_paise"]) == (4_800_000, 192_000)
    assert (local["handling_paise"], local["transport_paise"]) == (120_000, 300_000)
    assert local["net_paise"] == 4_188_000
    assert distant["transport_paise"] == 900_000
    assert distant["net_paise"] == 4_279_200


@pytest.mark.parametrize("fee_bp", [0, 150, 333, 10_000])
def test_breakdown_always_sums_to_net(fee_bp):
    r = net_realisation(
        quantity_kg=3_337,
        modal_paise_per_quintal=123_457,
        min_paise_per_quintal=100_001,
        max_paise_per_quintal=150_003,
        commission_bp=275,
        market_fee_bp=fee_bp,
        handling_paise_per_quintal=2_999,
        transport_paise=456_789,
    )
    deductions = sum(
        r[k] for k in ("commission_paise", "market_fee_paise", "handling_paise", "transport_paise")
    )
    assert r["gross_paise"] - deductions == r["net_paise"]


def test_market_fee_changes_the_ranking():
    # Same two offers; a 3% fee at the distant mandi only is enough to flip the order.
    near = {**worked(1200, Decimal(20)), "distance_m": 20_000, "market": "Near"}
    far = {**worked(1380, Decimal(60)), "distance_m": 60_000, "market": "Far"}
    assert [o["market"] for o in rank_offers([near, far])] == ["Far", "Near"]
    far_with_fee = {**worked(1380, Decimal(60), fee_bp=300), "distance_m": 60_000, "market": "Far"}
    assert far_with_fee["market_fee_paise"] == 165_600
    assert [o["market"] for o in rank_offers([near, far_with_fee])] == ["Near", "Far"]


def test_range_comes_from_reported_min_and_max():
    r = worked(1380, Decimal(60), low=1300, high=1450)
    assert r["net_min_paise"] < r["net_paise"] < r["net_max_paise"]
    # Only price-driven terms move: 80 q-rupees per quintal x 40 q less 4% commission.
    assert r["net_paise"] - r["net_min_paise"] == 80 * 40 * 100 * 96 // 100


def test_net_can_be_negative_and_is_reported_not_clamped():
    r = net_realisation(
        quantity_kg=100,
        modal_paise_per_quintal=5_000,
        min_paise_per_quintal=5_000,
        max_paise_per_quintal=5_000,
        commission_bp=0,
        market_fee_bp=0,
        handling_paise_per_quintal=0,
        transport_paise=100_000,
    )
    assert r["net_paise"] == -95_000


@pytest.mark.parametrize(
    "change",
    [
        {"min_paise_per_quintal": 130_000},  # min above modal
        {"max_paise_per_quintal": 110_000},  # max below modal
        {"commission_bp": 10_001},
        {"market_fee_bp": -1},
        {"quantity_kg": 0},
        {"transport_paise": -1},
        {"quantity_kg": 4000.0},  # floats never enter money arithmetic
    ],
)
def test_invalid_inputs_rejected(change):
    args = dict(
        quantity_kg=4_000,
        modal_paise_per_quintal=120_000,
        min_paise_per_quintal=110_000,
        max_paise_per_quintal=125_000,
        commission_bp=400,
        market_fee_bp=0,
        handling_paise_per_quintal=3_000,
        transport_paise=0,
    )
    with pytest.raises(TransportError):
        net_realisation(**{**args, **change})


def test_trip_cost_single_formula_half_up():
    assert trip_cost_paise(Decimal(1000), Decimal(10), Decimal(60)) == 160_000
    assert trip_cost_paise(Decimal(0), Decimal("0.005"), Decimal(1)) == 1
    with pytest.raises(TransportError):
        trip_cost_paise(Decimal(1000), Decimal(10), Decimal(-1))


def test_rank_ties_break_on_distance_then_name():
    same = {"net_paise": 100}
    ranked = rank_offers(
        [
            {**same, "distance_m": 5, "market": "B"},
            {**same, "distance_m": 5, "market": "A"},
            {**same, "distance_m": 1, "market": "Z"},
        ]
    )
    assert [(o["rank"], o["market"]) for o in ranked] == [(1, "Z"), (2, "A"), (3, "B")]
