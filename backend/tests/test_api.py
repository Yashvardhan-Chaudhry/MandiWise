from datetime import date, timedelta

import jwt
import pytest
from conftest import SECRET, approve, join, move, pool
from sqlalchemy.orm.exc import StaleDataError

from mandiwise_transport.cli import issue_token
from mandiwise_transport.db import Pool, User


def quote_body(s, **extra):
    return {
        "route_id": s["route_id"],
        "rate_card_id": s["rate_card_id"],
        "travel_date": s["travel_date"],
        "quantity_quintals": "40",
        **extra,
    }


def test_openapi_and_health(system):
    c = system["client"]
    assert c.get("/health").status_code == 200
    spec = c.get("/openapi.json").json()
    assert "/v1/transport/quote" in spec["paths"]
    assert spec["paths"]["/v1/pools"]["post"]["security"]


def test_authentication_and_authorisation(system):
    s = system
    assert s["client"].get("/v1/locations").status_code == 401
    assert (
        s["client"].get("/v1/locations", headers={"Authorization": "Bearer fake"}).status_code
        == 401
    )
    assert s["post"]("/routes", {**s["common"], "distance_km": "60"}, "alice").status_code == 403
    assert s["get"]("/me", "alice").json()["id"] == s["ids"]["alice"]
    expired = issue_token(s["ids"]["alice"], SECRET, -1)
    assert (
        s["client"].get("/v1/me", headers={"Authorization": "Bearer " + expired}).status_code == 401
    )
    invalid = jwt.encode({"sub": s["ids"]["alice"]}, SECRET, algorithm="HS256")
    assert (
        s["client"].get("/v1/me", headers={"Authorization": "Bearer " + invalid}).status_code == 401
    )
    with s["app"].state.sessions() as db:
        db.get(User, s["ids"]["alice"]).active = False
        db.commit()
    assert s["get"]("/me", "alice").status_code == 401


def test_quote_has_provenance_and_exact_cost(system):
    response = system["post"]("/transport/quote", quote_body(system), "alice")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cost_inr"] == "3200.00"
    assert body["capacity_kg"] == 6000
    assert body["is_demo"] is True
    assert body["distance_source"] == "Synthetic test fixture"
    assert len(body["warnings"]) == 4


@pytest.mark.parametrize("quantity", ["0", "-1", "0.001", "1000.01", "NaN", "Infinity"])
def test_api_rejects_bad_quantity(system, quantity):
    assert (
        system["post"](
            "/transport/quote", quote_body(system, quantity_quintals=quantity)
        ).status_code
        == 422
    )


def test_missing_stale_and_mismatched_inputs(system):
    s = system
    assert s["post"]("/transport/quote", quote_body(s, route_id="unknown")).status_code == 404
    assert (
        s["post"](
            "/transport/quote", quote_body(s, travel_date=str(date.today() + timedelta(days=31)))
        ).status_code
        == 409
    )
    other = s["post"](
        "/locations",
        {
            "name": "Another",
            "kind": "mandi",
            "state": "Punjab",
            "district": "Patiala",
            "source": "test",
        },
    ).json()["id"]
    route = s["post"](
        "/routes", {**s["common"], "destination_id": other, "distance_km": "25"}
    ).json()
    assert (
        s["post"]("/transport/quote", quote_body(s, route_id=route["id"])).json()["error"]["code"]
        == "rate_route_mismatch"
    )


def test_duplicate_participants_and_excess_pool_quantity(system):
    body = quote_body(system)
    del body["quantity_quintals"]
    body["participants"] = [{"participant_id": "a", "quantity_quintals": "40"}] * 2
    assert system["post"]("/transport/pool-quote", body).status_code == 422
    body["participants"] = [
        {"participant_id": name, "quantity_quintals": "600"} for name in ["a", "b"]
    ]
    assert system["post"]("/transport/pool-quote", body).status_code == 422


def test_complete_pool_lifecycle(system):
    s = system
    p = pool(s)
    path = f"/pools/{p['id']}"
    assert join(s, p["id"]).status_code == 201
    assert join(s, p["id"], "bob").status_code == 201
    assert approve(s, p["id"]).status_code == 200
    assert approve(s, p["id"], "bob").status_code == 200
    locked = move(s, p["id"], "LOCKED")
    assert locked.status_code == 200, locked.text
    assert locked.json()["locked_quote"]["cost_inr"] == "3700.00"
    assert (
        s["post"](
            path + "/withdraw", {"expected_version": locked.json()["version"]}, "alice"
        ).status_code
        == 409
    )
    assert move(s, p["id"], "DISPATCHED").status_code == 422
    dispatched = move(s, p["id"], "DISPATCHED", transport_reference="Coordinator arrangement #1")
    assert dispatched.status_code == 200
    assert move(s, p["id"], "CANCELLED", note="test").status_code == 409
    settled = move(
        s, p["id"], "SETTLED", note="Trip completed; amounts remain estimates; no payment processed"
    )
    assert settled.status_code == 200
    assert settled.json()["locked_quote"] == locked.json()["locked_quote"]
    assert move(s, p["id"], "LOCKED").status_code == 409
    assert len(s["get"](path + "/events", "coord").json()) == 8


def test_privacy_and_ownership(system):
    s = system
    p = pool(s)
    path = f"/pools/{p['id']}"
    assert s["get"](path, "alice").status_code == 403
    assert join(s, p["id"]).status_code == 201
    assert join(s, p["id"], "bob").status_code == 201
    assert len(s["get"](path, "alice").json()["members"]) == 1
    assert len(s["get"](path, "coord").json()["members"]) == 2
    assert s["get"](path + "/events", "bob").status_code == 403
    response = s["post"](
        path + "/transition",
        {"expected_version": 3, "target": "CANCELLED", "note": "unauthorised"},
        "other_coord",
    )
    assert response.status_code == 403


def test_capacity_duplicates_pending_and_stale_version(system):
    s = system
    p = pool(s, "60")
    assert move(s, p["id"], "LOCKED").json()["error"]["code"] == "empty_pool"
    assert join(s, p["id"]).status_code == 201
    assert join(s, p["id"]).status_code == 409
    assert move(s, p["id"], "LOCKED").json()["error"]["code"] == "pending_members"
    assert approve(s, p["id"]).status_code == 200
    assert join(s, p["id"], "bob").status_code == 201
    assert approve(s, p["id"], "bob").json()["error"]["code"] == "capacity_exceeded"
    assert (
        s["post"](
            f"/pools/{p['id']}/transition", {"expected_version": 1, "target": "LOCKED"}, "coord"
        ).json()["error"]["code"]
        == "version_conflict"
    )


def test_optimistic_concurrency_prevents_lost_updates(system):
    s = system
    p = pool(s)
    factory = s["app"].state.sessions
    with factory() as first, factory() as second:
        a, b = first.get(Pool, p["id"]), second.get(Pool, p["id"])
        a.version += 1
        first.commit()
        b.version += 1
        with pytest.raises(StaleDataError):
            second.commit()


def test_withdrawal_and_cancellation(system):
    s = system
    p = pool(s)
    joined = join(s, p["id"]).json()
    result = s["post"](
        f"/pools/{p['id']}/withdraw", {"expected_version": joined["version"]}, "alice"
    )
    assert result.status_code == 200
    assert result.json()["members"][0]["status"] == "WITHDRAWN"
    assert move(s, p["id"], "CANCELLED", note="No transport available").status_code == 200


def test_secret_is_required():
    from mandiwise_transport.api import create_app

    with pytest.raises(RuntimeError):
        create_app(jwt_secret="short")


def test_withdraw_and_rejoin_requires_new_approval(system):
    s = system
    p = pool(s)
    initial = join(s, p["id"]).json()
    s["post"](f"/pools/{p['id']}/withdraw", {"expected_version": initial["version"]}, "alice")
    new = join(s, p["id"], quantity="20")
    assert new.status_code == 201
    assert new.json()["members"][0]["quantity_kg"] == 2000
    assert new.json()["members"][0]["status"] == "PENDING"
    assert len(s["get"]("/me/pools", "alice").json()) == 1


def test_other_member_share_is_not_visible_after_lock(system):
    s = system
    p = pool(s)
    for name in ["alice", "bob"]:
        join(s, p["id"], name)
        approve(s, p["id"], name)
    move(s, p["id"], "LOCKED")
    response = s["post"](f"/pools/{p['id']}/quote", None, "alice")
    participants = response.json()["participants"]
    assert len(participants) == 1
    assert participants[0]["participant_id"] == s["ids"]["alice"]


def test_invalid_rates_and_spoofed_identity_rejected(system):
    s = system
    invalid = {
        **s["common"],
        "name": "bad",
        "vehicles": [
            {"code": "truck", "capacity_quintals": "100", "base_cost_inr": "0", "per_km_inr": "0"}
        ],
    }
    assert s["post"]("/rate-cards", invalid).status_code == 422
    assert (
        s["post"]("/transport/quote", {**quote_body(s), "user_id": s["ids"]["bob"]}).status_code
        == 422
    )


def test_lock_refuses_individual_cost_increase(system):
    s = system
    card = s["post"](
        "/rate-cards",
        {
            **s["common"],
            "name": "unbalanced",
            "vehicles": [
                {
                    "code": "small",
                    "capacity_quintals": "1",
                    "base_cost_inr": "100",
                    "per_km_inr": "0",
                },
                {
                    "code": "large",
                    "capacity_quintals": "9",
                    "base_cost_inr": "101",
                    "per_km_inr": "0",
                },
            ],
        },
    ).json()
    s["rate_card_id"] = card["id"]
    p = pool(s)
    join(s, p["id"], "alice", "1")
    join(s, p["id"], "bob", "9")
    approve(s, p["id"], "alice")
    approve(s, p["id"], "bob")
    response = move(s, p["id"], "LOCKED")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "member_cost_increase"
    assert s["get"](f"/pools/{p['id']}", "coord").json()["state"] == "OPEN"
