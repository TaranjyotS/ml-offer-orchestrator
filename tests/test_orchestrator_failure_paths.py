import respx
from fastapi.testclient import TestClient

from src.orchestrator.orchestrator_app import app


@respx.mock
def test_prediction_service_failure_returns_502():
    """If prediction service fails, orchestrator should return 502 (bad gateway)."""
    with TestClient(app) as client:
        respx.get("http://localhost:8001/member_data/A0F18FAA").respond(200, json=[])

        # ATS prediction fails
        respx.post("http://localhost:8002/ml/ats/predict").respond(500, json={"error": "model failure"})
        # RESP prediction (may still be attempted depending on timing, but will be mocked)
        respx.post("http://localhost:8002/ml/resp/predict").respond(200, json={"prediction": 0.3})

        payload = {
            "memberId": "A0F18FAA",
            "lastTransactionUtcTs": "2019-01-04T17:25:28+00:00",
            "lastTransactionType": "BUY",
            "lastTransactionPointsBought": 500,
            "lastTransactionRevenueUsd": 2.5,
        }

        resp = client.post("/member/offer", json=payload)
        assert resp.status_code == 502
        body = resp.json()
        assert body["detail"]["service"] in ("prediction", "offer_engine", "member_data")


@respx.mock
def test_offer_engine_failure_returns_502():
    """If offer engine fails, orchestrator should return 502 (bad gateway)."""
    with TestClient(app) as client:
        respx.get("http://localhost:8001/member_data/A0F18FAA").respond(200, json=[])

        respx.post("http://localhost:8002/ml/ats/predict").respond(200, json={"prediction": 100})
        respx.post("http://localhost:8002/ml/resp/predict").respond(200, json={"prediction": 0.4})

        # Offer engine fails
        respx.post("http://localhost:8003/offer/assign").respond(500, json={"error": "offer engine down"})

        payload = {
            "memberId": "A0F18FAA",
            "lastTransactionUtcTs": "2019-01-04T17:25:28+00:00",
            "lastTransactionType": "GIFT",
            "lastTransactionPointsBought": 500,
            "lastTransactionRevenueUsd": 2.5,
        }

        resp = client.post("/member/offer", json=payload)
        assert resp.status_code == 502
        body = resp.json()
        assert body["detail"]["service"] == "offer_engine"
