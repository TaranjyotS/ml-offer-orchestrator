from fastapi.testclient import TestClient

from src.orchestrator.orchestrator_app import app

client = TestClient(app)


def test_orchestrator_health_endpoint():
    """
    Health endpoint should always return 200 if app is running.
    """

    resp = client.get("/health")

    assert resp.status_code == 200
