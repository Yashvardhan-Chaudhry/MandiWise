from __future__ import annotations

import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from mandiwise.models import MandiOffer, PriceObservation, VehicleType
from mandiwise.recommendation import calculate_recommendation, rank_mandis


TEMPO = VehicleType("Tempo", Decimal("30"), Decimal("0"), Decimal("75"))
TRUCK = VehicleType("Truck", Decimal("100"), Decimal("0"), Decimal("100"))


def offer(name: str, price: str, distance: str) -> MandiOffer:
    return MandiOffer(
        price=PriceObservation(name, "Potato", Decimal(price), date(2026, 9, 17)),
        distance_km=Decimal(distance),
        commission_rate=Decimal("0.04"),
        handling_cost_per_quintal=Decimal("30"),
    )


class RecommendationTests(unittest.TestCase):
    def test_project_worked_example_matches_exact_amounts(self) -> None:
        local = calculate_recommendation(offer("Mandi A", "1200", "20"), 40, [TEMPO])
        distant = calculate_recommendation(offer("Mandi B", "1380", "60"), 40, [TEMPO])
        self.assertEqual(local.transport_inr, Decimal("3000.00"))
        self.assertEqual(local.net_realisation_inr, Decimal("41880.00"))
        self.assertEqual(distant.transport_inr, Decimal("9000.00"))
        self.assertEqual(distant.net_realisation_inr, Decimal("42792.00"))

    def test_mandis_are_ordered_by_net_not_headline_price(self) -> None:
        ranked = rank_mandis(
            [offer("Local", "1200", "20"), offer("Far but expensive", "1400", "100")],
            40,
            [TEMPO],
        )
        self.assertEqual(ranked[0].mandi_name, "Local")

    def test_invalid_quantity_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            calculate_recommendation(offer("Any", "1200", "20"), 0, [TEMPO])

    def test_old_price_is_flagged_not_silently_reused(self) -> None:
        old = MandiOffer(
            price=PriceObservation("Old", "Potato", Decimal("1200"), date(2026, 9, 10)),
            distance_km=Decimal("20"), commission_rate=Decimal("0.04"), handling_cost_per_quintal=Decimal("30"),
        )
        result = calculate_recommendation(old, 20, [TEMPO], today=date(2026, 9, 17))
        self.assertTrue(result.is_stale)

    def test_same_mandi_name_twice_keeps_each_offers_own_distance(self) -> None:
        """Two offers from one mandi must each tie-break on their own distance.

        Real data has a single market reporting two varieties of one commodity
        on the same day, so duplicate mandi names do reach rank_mandis.
        Distances used to be looked up by mandi name, so one offer's distance
        overwrote the other's and both rows tie-broke on whichever survived.

        Prices here are chosen so the two nets land exactly equal despite very
        different distances, which is what forces the tie-break to decide.
        """
        near = offer("Ghanaur", "1200", "15")    # transport 2 x 75 x 15  = 2250
        far = offer("Ghanaur", "1575", "111")    # transport 2 x 75 x 111 = 16650
        ranked = rank_mandis([far, near], 40, [TEMPO], today=date(2026, 9, 17))

        self.assertEqual(
            ranked[0].net_realisation_inr,
            ranked[1].net_realisation_inr,
            "test is only meaningful if the nets actually tie",
        )
        self.assertEqual(ranked[0].transport_inr, Decimal("2250.00"))
        self.assertEqual(ranked[1].transport_inr, Decimal("16650.00"))


if __name__ == "__main__":
    unittest.main()
