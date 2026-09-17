import random
from decimal import Decimal
from itertools import product

import pytest

from mandiwise_transport.engine import (
    TransportError,
    Vehicle,
    allocate_cost,
    kg,
    optimise,
    paise,
    pool_quote,
)


@pytest.mark.parametrize("quantity,count", [(2999, 1), (3000, 1), (3001, 2), (6000, 2), (6001, 3)])
def test_capacity_boundaries(quantity, count):
    result = optimise(quantity, [Vehicle("tempo", 3000, 160000)])
    assert result["vehicle_count"] == count
    assert result["capacity_kg"] >= quantity


def test_120_quintals_cannot_fit_in_100_quintal_truck():
    result = optimise(12000, [Vehicle("tempo", 3000, 160000), Vehicle("truck", 10000, 370000)])
    assert result["cost_inr"] == "5300.00"
    assert result["capacity_kg"] == 13000
    assert result["vehicle_count"] == 2


def test_optimiser_against_exhaustive_small_fleets():
    rng = random.Random(713)
    for _ in range(100):
        options = [Vehicle(str(i), rng.randint(2, 10), rng.randint(1, 50)) for i in range(3)]
        quantity = rng.randint(1, 20)
        brute = min(
            (
                sum(n * v.cost_paise for n, v in zip(counts, options)),
                sum(counts),
                sum(n * v.capacity_kg for n, v in zip(counts, options)),
            )
            for counts in product(range(11), repeat=3)
            if sum(n * v.capacity_kg for n, v in zip(counts, options)) >= quantity
        )
        got = optimise(quantity, options)
        assert (got["cost_paise"], got["vehicle_count"], got["capacity_kg"]) == brute


def test_paisa_conservation_and_stable_ties():
    assert allocate_cost(100, {"c": 1, "b": 1, "a": 1}) == {"a": 34, "b": 33, "c": 33}
    rng = random.Random(23)
    for _ in range(200):
        quantities = {str(i): rng.randint(1, 10000) for i in range(10)}
        total = rng.randint(1, 1000000)
        shares = allocate_cost(total, quantities)
        assert sum(shares.values()) == total
        assert all(
            abs(Decimal(shares[k]) - Decimal(total) * q / sum(quantities.values())) < 1
            for k, q in quantities.items()
        )


def test_pool_shares_are_cost_not_savings():
    result = pool_quote(
        {"a": 4000, "b": 4000}, [Vehicle("tempo", 3000, 160000), Vehicle("truck", 10000, 370000)]
    )
    assert result["cost_inr"] == "3700.00"
    assert result["total_savings_inr"] == "2700.00"
    assert {p["share_inr"] for p in result["participants"]} == {"1850.00"}


def test_group_savings_do_not_guarantee_individual_savings():
    result = pool_quote(
        {"small": 10, "large": 90}, [Vehicle("small", 10, 100), Vehicle("big", 100, 2000)]
    )
    # Identical per-kg rates above don't disadvantage anybody; use discontinuous rates.
    result = pool_quote(
        {"small": 10, "large": 90}, [Vehicle("small", 10, 100), Vehicle("big", 90, 101)]
    )
    assert result["all_participants_benefit"] is False
    assert any(Decimal(p["savings_inr"]) < 0 for p in result["participants"])


@pytest.mark.parametrize("value", ["0", "-1", "0.001", "1000.01", "NaN", "Infinity"])
def test_invalid_quantities(value):
    with pytest.raises(TransportError):
        kg(Decimal(value))


def test_half_up_unit_cost():
    assert paise(Decimal("1.005")) == 101


def test_deterministic_tie():
    options = [Vehicle("z", 100, 20), Vehicle("a", 100, 20)]
    assert optimise(50, options)["vehicles"][0]["code"] == "a"


def test_empty_and_free_options_rejected():
    for options in ([], [Vehicle("free", 100, 0)]):
        with pytest.raises(TransportError):
            optimise(100, options)
