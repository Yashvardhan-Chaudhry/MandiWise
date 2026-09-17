"""Opt-in synthetic demonstration against a running LOCAL development API.

Uses DATABASE_URL and JWT_SECRET to provision local test identities; do not run
against production. Tokens are passed to the loopback server, never printed.
"""

import argparse
import json
import os
from datetime import timedelta
from uuid import uuid4

import httpx

from mandiwise_transport.cli import issue_token
from mandiwise_transport.db import User, database
from mandiwise_transport.services import today


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    secret = os.environ["JWT_SECRET"]
    suffix = uuid4().hex[:8]
    engine, sessions = database()
    users = {}
    with sessions() as db:
        for name, role in [
            ("admin", "admin"),
            ("coordinator", "coordinator"),
            ("farmer", "farmer"),
        ]:
            user = User(name=f"DEMO {name} {suffix}", role=role)
            db.add(user)
            db.flush()
            users[name] = user.id
        db.commit()
    tokens = {name: issue_token(uid, secret) for name, uid in users.items()}
    with httpx.Client(base_url=f"http://127.0.0.1:{args.port}", timeout=30) as client:

        def call(path, body=None, actor="admin", method="POST"):
            response = client.request(
                method,
                "/v1" + path,
                json=body,
                headers={"Authorization": "Bearer " + tokens[actor]},
            )
            response.raise_for_status()
            return response.json()

        origin = call(
            "/locations",
            {
                "name": f"DEMO pickup {suffix}",
                "kind": "origin",
                "state": "Punjab",
                "district": "Patiala",
                "source": "Synthetic demo only",
            },
        )
        mandi = call(
            "/locations",
            {
                "name": f"DEMO mandi {suffix}",
                "kind": "mandi",
                "state": "Punjab",
                "district": "Patiala",
                "source": "Synthetic demo only",
            },
        )
        common = {
            "origin_id": origin["id"],
            "destination_id": mandi["id"],
            "source": "Synthetic demo only; not a verified distance or supplier quotation",
            "effective_from": str(today()),
            "effective_until": str(today() + timedelta(days=7)),
        }
        route = call("/routes", {**common, "distance_km": "60"})
        card = call(
            "/rate-cards",
            {
                **common,
                "name": f"DEMO rates {suffix}",
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
        )
        route_info = {
            "route_id": route["id"],
            "rate_card_id": card["id"],
            "travel_date": str(today()),
        }
        solo = call("/transport/quote", {**route_info, "quantity_quintals": "40"}, "farmer")
        pool = call(
            "/pools",
            {
                **route_info,
                "commodity": "Potato",
                "max_quantity_quintals": "100",
                "pickup_description": "DEMO shared pickup; keep both lots separately bagged",
            },
            "coordinator",
        )
        path = "/pools/" + pool["id"]
        lot = {
            "quantity_quintals": "40",
            "variety": "Potato",
            "grade": "Declared A",
            "condition": "Demo declaration: separately tagged bags",
        }
        for actor in ("coordinator", "farmer"):
            call(path + "/join", lot, actor)
        state = call(path, actor="coordinator", method="GET")
        for member in state["members"]:
            state = call(
                path + f"/members/{member['id']}/review",
                {"expected_version": state["version"], "decision": "APPROVED"},
                "coordinator",
            )
        locked = call(
            path + "/transition",
            {"expected_version": state["version"], "target": "LOCKED"},
            "coordinator",
        )
        state = call(
            path + "/transition",
            {
                "expected_version": locked["version"],
                "target": "DISPATCHED",
                "transport_reference": "Synthetic demonstration; no real vehicle booked",
            },
            "coordinator",
        )
        state = call(
            path + "/transition",
            {
                "expected_version": state["version"],
                "target": "SETTLED",
                "note": "Synthetic demonstration completed; no money moved",
            },
            "coordinator",
        )
        assert solo["cost_inr"] == "3200.00"
        assert locked["locked_quote"]["cost_inr"] == "3700.00"
        assert state["state"] == "SETTLED"
        print(
            json.dumps(
                {
                    "demo": True,
                    "pool_id": pool["id"],
                    "state": state["state"],
                    "solo_40_quintals_inr": solo["cost_inr"],
                    "shared_80_quintals": locked["locked_quote"],
                },
                indent=2,
            )
        )
    engine.dispose()


if __name__ == "__main__":
    main()
