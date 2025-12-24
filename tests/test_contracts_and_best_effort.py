# tests/test_contracts_and_best_effort.py
import json
import httpx
import respx
from fastapi.testclient import TestClient

from src.orchestrator.orchestrator_app import app


@respx.mock
def test_offer_engine_contract_payload_shape():
    """
    Assert we call offer_engine with the expected contract:
      { "ats_prediction": float, "resp_prediction": float }
    """
    with TestClient(app) as client:
        respx.get("http://localhost:8001/member_data/A0F18FAA").respond(404)
        respx.post("http://localhost:8002/ml/ats/predict").respond(200, json={"prediction": 0.8})
        respx.post("http://localhost:8002/ml/resp/predict").respond(200, json={"prediction": 0.2})

        def offer_cb(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            assert set(data.keys()) == {"ats_prediction", "resp_prediction"}
            assert isinstance(data["ats_prediction"], (int, float))
            assert isinstance(data["resp_prediction"], (int, float))
            return httpx.Response(200, json={"offer": "OFFER_A"})

        respx.post("http://localhost:8003/offer/assign").mock(side_effect=offer_cb)
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
        body = resp.json()
        assert body["memberId"] == "A0F18FAA"
        assert body["offer"] == "OFFER_A"


@respx.mock
def test_member_data_store_failure_is_best_effort_and_does_not_fail_request():
    """
    Test that there is 'no single point of failure':
    even if storing transaction fails, caller still gets offer response.
    """
    with TestClient(app) as client:
        respx.get("http://localhost:8001/member_data/A0F18FAA").respond(200, json=[])
        respx.post("http://localhost:8002/ml/ats/predict").respond(200, json={"prediction": 1.0})
        respx.post("http://localhost:8002/ml/resp/predict").respond(200, json={"prediction": 0.9})
        respx.post("http://localhost:8003/offer/assign").respond(200, json={"offer": "OFFER_A"})

        # Store fails (simulates DB error / downstream outage)
        respx.post("http://localhost:8001/member_data").respond(500, json={"error": "db down"})

        payload = {
            "memberId": "A0F18FAA",
            "lastTransactionUtcTs": "2019-01-04T17:25:28+00:00",
            "lastTransactionType": "BUY",
            "lastTransactionPointsBought": 500.0,
            "lastTransactionRevenueUsd": 2.5,
        }

        resp = client.post("/member/offer", json=payload)

        assert resp.status_code == 200
        assert resp.json()["offer"] == "OFFER_A"
