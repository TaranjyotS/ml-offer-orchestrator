import respx
from fastapi.testclient import TestClient

from src.orchestrator.orchestrator_app import app


def test_orchestrator_path():
    with TestClient(app) as client:
        with respx.mock(assert_all_called=True) as rs:
            rs.get("http://localhost:8001/member_data/A0F18FAA").respond(404)
            rs.post("http://localhost:8002/ml/ats/predict").respond(200, json={"prediction": 0.8})
            rs.post("http://localhost:8002/ml/resp/predict").respond(200, json={"prediction": 0.2})
            rs.post("http://localhost:8003/offer/assign").respond(200, json={"offer": "OFFER_A"})
            rs.post("http://localhost:8001/member_data").respond(200, json={"status": "ok"})

            payload = {
                "memberId": "A0F18FAA",
                "lastTransactionUtcTs": "2019-01-04T17:25:28+00:00",
                "lastTransactionType": "GIFT",
                "lastTransactionPointsBought": 500.0,
                "lastTransactionRevenueUsd": 2.5,
            }

            r = client.post("/member/offer", json=payload)
            assert r.status_code == 200
            body = r.json()
            assert body["memberId"] == "A0F18FAA"
            assert body["offer"] == "OFFER_A"


def test_orchestrator_422_for_bad_payload():
    with TestClient(app) as client:
        # missing required fields
        r = client.post("/member/offer", json={"memberId": "X"})
        assert r.status_code == 422
