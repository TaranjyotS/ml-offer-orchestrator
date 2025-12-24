import respx
from fastapi.testclient import TestClient

from src.orchestrator.orchestrator_app import app


@respx.mock
def test_request_id_is_propagated_back_to_client_when_provided():
    with TestClient(app) as client:
        # Mock upstreams
        respx.get("http://localhost:8001/member_data/A0F18FAA").respond(404)
        respx.post("http://localhost:8002/ml/ats/predict").respond(200, json={"prediction": 0.8})
        respx.post("http://localhost:8002/ml/resp/predict").respond(200, json={"prediction": 0.2})
        respx.post("http://localhost:8003/offer/assign").respond(200, json={"offer": "OFFER_A"})

        respx.post("http://localhost:8001/member_data").respond(200, json={"status": "ok"})

        payload = {
            "memberId": "A0F18FAA",
            "lastTransactionUtcTs": "2019-01-04T17:25:28+00:00",
            "lastTransactionType": "GIFT",
            "lastTransactionPointsBought": 500.0,
            "lastTransactionRevenueUsd": 2.5,
        }

        rid = "panel-demo-request-id-123"
        resp = client.post("/member/offer", json=payload, headers={"X-Request-ID": rid})

        assert resp.status_code == 200
        assert resp.headers.get("X-Request-ID") == rid


@respx.mock
def test_request_id_is_generated_when_missing():
    with TestClient(app) as client:
        respx.get("http://localhost:8001/member_data/A0F18FAA").respond(404)
        respx.post("http://localhost:8002/ml/ats/predict").respond(200, json={"prediction": 0.8})
        respx.post("http://localhost:8002/ml/resp/predict").respond(200, json={"prediction": 0.2})
        respx.post("http://localhost:8003/offer/assign").respond(200, json={"offer": "OFFER_A"})
        respx.post("http://localhost:8001/member_data").respond(200, json={"status": "ok"})

        payload = {
            "memberId": "A0F18FAA",
            "lastTransactionUtcTs": "2019-01-04T17:25:28+00:00",
            "lastTransactionType": "GIFT",
            "lastTransactionPointsBought": 500.0,
            "lastTransactionRevenueUsd": 2.5,
        }

        resp = client.post("/member/offer", json=payload)
        assert resp.status_code == 200

        rid = resp.headers.get("X-Request-ID")
        assert rid is not None
        assert rid != ""
