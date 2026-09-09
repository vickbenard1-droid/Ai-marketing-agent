"""
Regression test for a real gap found during the Week 12 monitoring
review: /health (the endpoint backend/Dockerfile's own HEALTHCHECK
directive points at) was a pure liveness probe with zero database
dependency verification - a completely broken DB connection would have
been invisible to it, meaning container orchestration would keep
routing real traffic to a container that cannot actually serve any real
request.
"""
from unittest.mock import MagicMock

from app.db.session import get_db
from app.main import app


def test_health_check_returns_200_with_a_working_database(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_check_returns_503_when_database_is_unreachable(client):
    """The actual regression test for the fixed gap."""
    broken_db = MagicMock()
    broken_db.execute.side_effect = Exception("simulated real DB connection failure")

    def override_broken_db():
        yield broken_db

    app.dependency_overrides[get_db] = override_broken_db
    try:
        resp = client.get("/health")
        assert resp.status_code == 503
        assert "Database connectivity check failed" in resp.json()["detail"]
    finally:
        del app.dependency_overrides[get_db]
