"""Ranking API: public, read-only, placeholder-labelled, and arithmetic-free in the route."""

import json
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from mandiwise_transport.api import DEFAULT_DATA_DIR, create_app

SECRET = "transport-tests-only-secret-32-bytes-long"


def row(market, modal, low=None, high=None, day="07/09/2026", district="Patiala", **extra):
    return {
        "state": "Punjab",
        "district": district,
        "market": market,
        "commodity": "Potato",
        "variety": "Local",
        "grade": "FAQ",
        "arrival_date": day,
        "min_price": low or modal,
        "max_price": high or modal,
        "modal_price": modal,
        **extra,
    }


@pytest.fixture
def client(tmp_path):
    snapshot = [
        row("Near APMC", 1200, 1100, 1250),
        row("Far APMC", 1380, 1300, 1450),
        row("Far APMC", 1000, day="01/09/2026"),  # older duplicate: superseded
        row("Old APMC", 1500, day="01/09/2026"),  # latest is 6 days old: stale
        row("Junk APMC", 0.08),  # below the Rs 50 floor: rejected
        row("Bad APMC", 900, 1000, 1100),  # modal outside min/max: rejected
    ]
    (tmp_path / "punjab_2026-09-07.json").write_text(json.dumps(snapshot))
    (tmp_path / "vehicle_rates.json").write_text((DEFAULT_DATA_DIR / "vehicle_rates.json").read_text())
    (tmp_path / "market_rates.json").write_text((DEFAULT_DATA_DIR / "market_rates.json").read_text())
    app = create_app("sqlite://", SECRET, data_dir=tmp_path)
    app.state.today = lambda: date(2026, 9, 7)
    with TestClient(app) as c:
        yield c


def rank(client, candidates, quantity="40", commodity="potato"):
    body = {"commodity": commodity, "quantity_quintals": quantity, "candidates": candidates}
    return client.post("/v1/rankings", json=body)


def test_ranking_matches_demo_example_on_canonical_placeholder_card(client):
    # Same inputs as demo.py: 40 q, A Rs 1200 at 20 km, B Rs 1380 at 60 km.
    r = rank(
        client,
        [{"market": "Near APMC", "distance_km": "20"}, {"market": "far apmc", "distance_km": "60"}],
    )
    assert r.status_code == 200
    body = r.json()
    first, second = body["results"]
    assert (first["market"], first["net"], first["transport"]) == ("Far APMC", "48592.00", "3200.00")
    assert (second["market"], second["net"], second["transport"]) == ("Near APMC", "42480.00", "2400.00")
    assert (first["net_min"], first["net_max"]) == ("45520.00", "51280.00")
    for result in body["results"]:
        deductions = sum(
            Decimal(result[k]) for k in ("commission", "market_fee", "handling", "transport")
        )
        assert Decimal(result["gross"]) - deductions == Decimal(result["net"])
    assert body["is_demo"] is True
    assert any("PLACEHOLDER market rates" in w for w in body["warnings"])
    assert any("Market fee" in w for w in body["warnings"])
    assert body["rates"]["source"].startswith("PLACEHOLDER")
    assert body["vehicle_rates"]["source"].startswith("PLACEHOLDER")


def test_stale_price_is_flagged_not_hidden(client):
    body = rank(client, [{"market": "Old APMC", "distance_km": "10"}]).json()
    (result,) = body["results"]
    assert (result["price_date"], result["age_days"], result["is_stale"]) == ("2026-09-01", 6, True)
    assert any("more than 2 days old" in w for w in body["warnings"])


def test_unknown_and_rejected_markets_are_reported_unmatched(client):
    body = rank(
        client,
        [
            {"market": "Nowhere", "distance_km": "5"},
            {"market": "Junk APMC", "distance_km": "5"},
            {"market": "Bad APMC", "distance_km": "5"},
        ],
    ).json()
    assert body["results"] == []
    assert [u["market"] for u in body["unmatched"]] == ["Nowhere", "Junk APMC", "Bad APMC"]


def test_markets_lists_latest_dated_prices_and_rejections(client):
    body = client.get("/v1/markets", params={"commodity": "Potato"}).json()
    by_market = {m["market"]: m for m in body["markets"]}
    assert set(by_market) == {"Near APMC", "Far APMC", "Old APMC"}
    assert by_market["Far APMC"]["modal_price"] == "1380.00"
    assert by_market["Near APMC"]["is_stale"] is False
    assert body["rejected_rows"] == {"unparseable": 0, "below_floor": 1, "outside_min_max": 1}
    assert client.get("/v1/commodities").json()["commodities"] == ["Potato"]


@pytest.mark.parametrize(
    "body",
    [
        {"commodity": "potato", "quantity_quintals": "0", "candidates": [{"market": "A", "distance_km": "1"}]},
        {"commodity": "potato", "quantity_quintals": "1001", "candidates": [{"market": "A", "distance_km": "1"}]},
        {"commodity": "potato", "quantity_quintals": "40", "candidates": []},
        {"commodity": "potato", "quantity_quintals": "40", "candidates": [{"market": "A", "distance_km": "-1"}]},
        {
            "commodity": "potato",
            "quantity_quintals": "40",
            "candidates": [{"market": f"M{i}", "distance_km": "1"} for i in range(11)],
        },
    ],
)
def test_inputs_are_capped(client, body):
    assert client.post("/v1/rankings", json=body).status_code == 422


def test_missing_snapshots_is_a_clear_503(tmp_path):
    app = create_app("sqlite://", SECRET, data_dir=tmp_path)
    with TestClient(app) as c:
        r = c.get("/v1/commodities")
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "prices_unavailable"


def test_committed_repository_data_loads():
    app = create_app("sqlite://", SECRET)
    with TestClient(app) as c:
        body = c.get("/v1/commodities").json()
    assert "Potato" in body["commodities"]
    assert "punjab_2026-09-04.json" in body["source"]
