# tests/test_retry_behavior.py
import respx
import httpx
from fastapi.testclient import TestClient

from src.orchestrator.orchestrator_app import app


@respx.mock
def test_prediction_500_fails_fast_and_returns_502():
    """
    Prediction service returning 500 should NOT be retried.
    Orchestrator must fail fast with 502 (Bad Gateway).
    """
    with TestClient(app) as client:
        respx.get("http://localhost:8001/member_data/A0F18FAA").respond(200, json=[])

        def ats_cb(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": "server failure"})

        respx.post("http://localhost:8002/ml/ats/predict").mock(side_effect=ats_cb)
        respx.post("http://localhost:8002/ml/resp/predict").respond(
            200, json={"prediction": 0.2}
        )

        payload = {
            "memberId": "A0F18FAA",
            "lastTransactionUtcTs": "2019-01-04T17:25:28+00:00",
            "lastTransactionType": "GIFT",
            "lastTransactionPointsBought": 500.0,
            "lastTransactionRevenueUsd": 2.5,
        }

        resp = client.post("/member/offer", json=payload)

        assert resp.status_code == 502
        detail = resp.json()["detail"]
        assert detail["service"] == "prediction"
        assert detail["status_code"] == 500
