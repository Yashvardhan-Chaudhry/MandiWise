from fastapi.testclient import TestClient

from mandiwise_transport.presentation import create_demo_app


def sample(quantities=("40", "40")):
    return {
        "distance_km": "60",
        "farmers": [
            {"name": f"Farmer {i}", "quantity_quintals": q} for i, q in enumerate(quantities)
        ],
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
    }


def test_presentation_needs_no_database_or_secret(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("DATABASE_URL", "not-a-database")
    with TestClient(create_demo_app("sqlite:///:memory:")) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "What will the trip cost?" in page.text
        assert "Classroom example" in page.text
        result = client.post("/demo/calculate", json=sample()).json()
        assert result["cost_inr"] == "3700.00"
        assert result["individual_total_inr"] == "6400.00"
        assert result["total_savings_inr"] == "2700.00"
        assert all(p["share_inr"] == "1850.00" for p in result["participants"])
        assert result["rate_breakdown"][0]["trip_cost_inr"] == "1600.00"
        assert client.get("/v1/me").status_code == 401


def test_presentation_capacity_and_changed_distance():
    with TestClient(create_demo_app("sqlite:///:memory:")) as client:
        result = client.post("/demo/calculate", json=sample(("40", "40", "40"))).json()
        assert result["cost_inr"] == "5300.00"
        assert result["vehicle_count"] == 2
        assert result["capacity_kg"] == 13000
        body = sample()
        body["distance_km"] = "100"
        assert client.post("/demo/calculate", json=body).json()["cost_inr"] == "4500.00"


def test_presentation_input_errors_and_duplicate_display_names():
    with TestClient(create_demo_app("sqlite:///:memory:")) as client:
        body = sample()
        body["farmers"][1]["name"] = body["farmers"][0]["name"]
        assert len(client.post("/demo/calculate", json=body).json()["participants"]) == 2
        body["farmers"] = []
        assert client.post("/demo/calculate", json=body).status_code == 422
        body = sample(("600", "600"))
        assert client.post("/demo/calculate", json=body).status_code == 422
        body = sample()
        body["distance_km"] = "0"
        assert client.post("/demo/calculate", json=body).status_code == 422
        body = sample()
        for v in body["vehicles"]:
            v["base_cost_inr"] = "0"
            v["per_km_inr"] = "0"
        assert client.post("/demo/calculate", json=body).status_code == 422


def test_existing_api_has_demo_without_changing_auth(system):
    assert system["client"].get("/").status_code == 200
    assert system["client"].get("/v1/me").status_code == 401
    assert system["client"].post("/demo/calculate", json=sample()).status_code == 200


def test_packaged_pages_and_static_assets(system):
    client = system["client"]
    for page, asset in [("/demo", "calculator"), ("/pooling", "pooling")]:
        response = client.get(page)
        assert response.status_code == 200
        assert f'/assets/{asset}.css' in response.text
        assert f'/assets/{asset}.js' in response.text
        for extension in ("css", "js"):
            resource = client.get(f"/assets/{asset}.{extension}")
            assert resource.status_code == 200
            assert len(resource.content) > 100
    assert "class VehicleEditor" in client.get("/assets/vehicles.js").text
    # Serve only the dedicated public asset folder, never Python source or databases.
    assert client.get("/assets/portal.py").status_code == 404
    assert client.get("/assets/portal.db").status_code == 404
