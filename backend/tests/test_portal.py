from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from mandiwise_transport import portal
from mandiwise_transport.db import PortalAccount
from mandiwise_transport.presentation import create_demo_app
from mandiwise_transport.services import today

HEADERS = {"X-MandiWise-Request": "portal", "Origin": "http://testserver"}
PASSWORD = "a long test password sentence"


@pytest.fixture
def clients(tmp_path):
    portal._attempts.clear()
    app = create_demo_app(f"sqlite:///{tmp_path / 'portal.db'}", "x" * 48)
    with (
        TestClient(app, headers=HEADERS) as a,
        TestClient(app, headers=HEADERS) as b,
        TestClient(app, headers=HEADERS) as c,
    ):
        for client, name in [(a, "alice"), (b, "bob"), (c, "carol")]:
            response = client.post(
                "/portal/api/register",
                json={
                    "username": name,
                    "password": PASSWORD,
                    "name": name.title(),
                    "village": "Test village",
                },
            )
            assert response.status_code == 201, response.text
            assert "HttpOnly" in response.headers["set-cookie"]
        yield a, b, c, app
    app.state.engine.dispose()


def trip():
    return {
        "origin": "Demo village",
        "destination": "Demo mandi",
        "state": "Punjab",
        "district": "Ludhiana",
        "travel_date": str(today() + timedelta(days=1)),
        "commodity": "Wheat",
        "pickup_description": "Collection centre",
        "distance_km": "60",
        "max_quantity_quintals": "100",
        "lot": lot(),
        "vehicles": [
            {
                "code": "truck",
                "name": "Large truck",
                "capacity_quintals": "100",
                "base_cost_inr": "2500",
                "per_km_inr": "20",
            }
        ],
    }


def lot():
    return {
        "quantity_quintals": "40",
        "variety": "Test variety",
        "grade": "Grade A",
        "condition": "Separate bags",
    }


def test_two_farmers_discovery_approval_chat_cost_and_persistence(clients):
    a, b, c, app = clients
    response = a.post("/portal/api/trips", json=trip())
    assert response.status_code == 201, response.text
    pool_id = response.json()["id"]
    base = f"/v1/pools/{pool_id}"
    custom = f"/portal/api/trips/{pool_id}"
    assert len(b.get("/portal/api/trips?search=wheat").json()) == 1
    assert b.get("/portal/api/trips?search=nonexistent").json() == []
    assert "members" not in c.get(custom).json()
    assert c.get(custom + "/workspace").json()["members"] == []
    assert b.get(custom + "/messages").status_code == 403
    joined = b.post(base + "/join", json=lot())
    assert joined.status_code == 201
    own = joined.json()["members"][0]
    assert own["status"] == "PENDING"
    assert b.post(custom + "/messages", json={"body": "not approved"}).status_code == 403
    view = a.get(base).json()
    assert (
        b.post(
            base + f"/members/{own['id']}/review",
            json={"decision": "APPROVED", "expected_version": view["version"]},
        ).status_code
        == 403
    )
    approved = a.post(
        base + f"/members/{own['id']}/review",
        json={"decision": "APPROVED", "expected_version": view["version"]},
    )
    assert approved.status_code == 200
    estimate = b.post(base + "/quote").json()
    assert len(estimate["participants"]) == 1
    assert estimate["participants"][0]["share_inr"] == "1850.00"
    assert b.post(custom + "/messages", json={"body": "Meet at 7 AM <script>"}).status_code == 201
    assert a.get(custom + "/messages").json()[0]["body"] == "Meet at 7 AM <script>"
    assert c.get(custom + "/messages").status_code == 403
    assert b.get(custom + "/workspace").json()["members"][0]["name"] == "Bob"
    locked = a.post(
        base + "/transition",
        json={"target": "LOCKED", "expected_version": approved.json()["version"]},
    )
    assert locked.status_code == 200, locked.text
    assert c.post(base + "/join", json=lot()).status_code == 409
    assert b.get("/portal/api/trips").json() == []
    assert len(b.get("/portal/api/mine").json()) == 1
    # New application instance reads the same persisted accounts, pools and messages.
    second = create_demo_app(str(app.state.engine.url), "x" * 48)
    with TestClient(second, headers=HEADERS) as fresh:
        assert (
            fresh.post(
                "/portal/api/login", json={"username": "bob", "password": PASSWORD}
            ).status_code
            == 200
        )
        assert fresh.get(custom + "/messages").json()[0]["name"] == "Bob"
    second.state.engine.dispose()


def test_password_auth_csrf_validation_and_no_admin_escalation(clients):
    a, b, c, app = clients
    with app.state.sessions() as db:
        account = db.scalar(select(PortalAccount).where(PortalAccount.username == "alice"))
        assert PASSWORD not in account.password_hash
        assert account.password_hash.startswith("scrypt$")
    assert (
        a.post(
            "/portal/api/trips", json=trip(), headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    a.headers.pop("X-MandiWise-Request")
    assert a.post("/portal/api/trips", json=trip()).status_code == 403
    a.headers.update(HEADERS)
    assert (
        a.post(
            "/v1/locations",
            json={"name": "x", "kind": "origin", "state": "x", "district": "x", "source": "x"},
        ).status_code
        == 403
    )
    assert a.post("/portal/api/logout", json={}).status_code == 200
    assert a.get("/v1/me").status_code == 401
    assert (
        a.post("/portal/api/login", json={"username": "alice", "password": "wrong"}).status_code
        == 401
    )
    assert (
        a.post("/portal/api/login", json={"username": "alice", "password": PASSWORD}).status_code
        == 200
    )
    bad = trip()
    bad["max_quantity_quintals"] = "20"
    assert a.post("/portal/api/trips", json=bad).status_code == 422
    bad = trip()
    bad["travel_date"] = str(today() - timedelta(days=1))
    assert a.post("/portal/api/trips", json=bad).status_code == 422
    assert a.get("/pooling").status_code == 200
    assert a.get("/demo/vehicles.js").status_code == 200


def test_withdrawal_removes_chat_access_and_custom_vehicle_quotes(clients):
    a, b, _, _app = clients
    t = a.post("/portal/api/trips", json=trip()).json()
    base = "/v1/pools/" + t["id"]
    joined = b.post(base + "/join", json=lot()).json()
    member = joined["members"][0]
    approved = a.post(
        base + f"/members/{member['id']}/review",
        json={"decision": "APPROVED", "expected_version": joined["version"]},
    ).json()
    assert (
        b.post(base + "/withdraw", json={"expected_version": approved["version"]}).status_code
        == 200
    )
    assert b.get("/portal/api/trips/" + t["id"] + "/messages").status_code == 403
    calc = {
        "distance_km": "10",
        "farmers": [{"name": "Test", "quantity_quintals": "10"}],
        "vehicles": [
            {
                "code": "mini_van",
                "name": "Mini van",
                "capacity_quintals": "20",
                "base_cost_inr": "100",
                "per_km_inr": "5",
            }
        ],
    }
    result = a.post("/demo/calculate", json=calc)
    assert result.json()["cost_inr"] == "150.00"
    calc["vehicles"] = []
    assert a.post("/demo/calculate", json=calc).status_code == 422
