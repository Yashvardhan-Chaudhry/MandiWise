from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from mandiwise_transport.api import create_app
from mandiwise_transport.cli import issue_token
from mandiwise_transport.db import Base, User

SECRET = "transport-tests-only-secret-32-bytes-long"


@pytest.fixture
def system(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'test.db'}", SECRET)
    Base.metadata.create_all(app.state.engine)
    ids = {}
    with app.state.sessions() as db:
        for name, role in [
            ("admin", "admin"),
            ("coord", "coordinator"),
            ("other_coord", "coordinator"),
            ("alice", "farmer"),
            ("bob", "farmer"),
        ]:
            user = User(name=name, role=role)
            db.add(user)
            db.flush()
            ids[name] = user.id
        db.commit()
    with TestClient(app) as client:

        def headers(name):
            return {"Authorization": "Bearer " + issue_token(ids[name], SECRET)}

        def post(path, data, name="admin"):
            return client.post("/v1" + path, json=data, headers=headers(name))

        def get(path, name="admin"):
            return client.get("/v1" + path, headers=headers(name))

        today = date.today()
        origin = post(
            "/locations",
            {
                "name": "DEMO shared pickup",
                "kind": "origin",
                "state": "Punjab",
                "district": "Patiala",
                "source": "Synthetic test fixture",
            },
        ).json()["id"]
        destination = post(
            "/locations",
            {
                "name": "DEMO mandi",
                "kind": "mandi",
                "state": "Punjab",
                "district": "Patiala",
                "source": "Synthetic test fixture",
            },
        ).json()["id"]
        common = {
            "origin_id": origin,
            "destination_id": destination,
            "source": "Synthetic test fixture",
            "effective_from": str(today),
            "effective_until": str(today + timedelta(days=30)),
        }
        route = post("/routes", {**common, "distance_km": "60.000"}).json()["id"]
        card = post(
            "/rate-cards",
            {
                **common,
                "name": "DEMO rates",
                "is_demo": True,
                "vehicles": [
                    {
                        "code": "tempo",
                        "capacity_quintals": "30",
                        "base_cost_inr": "1000",
                        "per_km_inr": "10",
                    },
                    {
                        "code": "truck",
                        "capacity_quintals": "100",
                        "base_cost_inr": "2500",
                        "per_km_inr": "20",
                    },
                ],
            },
        ).json()["id"]
        yield {
            "app": app,
            "client": client,
            "headers": headers,
            "post": post,
            "get": get,
            "ids": ids,
            "route_id": route,
            "rate_card_id": card,
            "travel_date": str(today),
            "common": common,
        }
    app.state.engine.dispose()


def pool(system, cap="100"):
    s = system
    result = s["post"](
        "/pools",
        {
            "route_id": s["route_id"],
            "rate_card_id": s["rate_card_id"],
            "travel_date": s["travel_date"],
            "commodity": "Potato",
            "pickup_description": "Meet at DEMO shared pickup; own lots separately bagged",
            "max_quantity_quintals": cap,
        },
        "coord",
    )
    assert result.status_code == 201, result.text
    return result.json()


def join(system, pool_id, name="alice", quantity="40"):
    return system["post"](
        f"/pools/{pool_id}/join",
        {
            "quantity_quintals": quantity,
            "variety": "Potato",
            "grade": "Declared A",
            "condition": "Fresh, separate bags",
        },
        name,
    )


def approve(system, pool_id, name="alice"):
    state = system["get"](f"/pools/{pool_id}", "coord").json()
    member = next(m for m in state["members"] if m["user_id"] == system["ids"][name])
    return system["post"](
        f"/pools/{pool_id}/members/{member['id']}/review",
        {"expected_version": state["version"], "decision": "APPROVED"},
        "coord",
    )


def move(system, pool_id, target, **kwargs):
    state = system["get"](f"/pools/{pool_id}", "coord").json()
    return system["post"](
        f"/pools/{pool_id}/transition",
        {"expected_version": state["version"], "target": target, **kwargs},
        "coord",
    )
