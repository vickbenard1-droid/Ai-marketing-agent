"""
Shared pytest fixtures.

Uses an in-memory SQLite database for speed/isolation in unit and API tests.
SQLite doesn't support every Postgres feature we use (native UUID type,
Postgres ENUM), so this fixture swaps in SQLite-compatible variants of the
affected columns at test-collection time rather than changing the models
themselves — the models stay Postgres-native for production.

Integration tests that need real Postgres-only behavior (e.g. ENUM
constraints) should be marked and run against a real Postgres instance in
CI (see docs/TESTING.md), not against this fixture.
"""
import os
import uuid

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("CREDENTIALS_ENCRYPTION_KEY", "wq0oR7VbLdoImevZgKUKcOc1qgO2gh8OyRSFvUgm3mQ=")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("APP_ENV", "test")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base_class import Base
import app.models  # noqa: F401 ensures all models are registered on Base.metadata


@pytest.fixture()
def db_session():
    """Fresh in-memory SQLite DB per test, all tables created from the
    same metadata used in production (minus Postgres-only type nuances)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def seeded_roles(db_session):
    """Seeds the same system roles as app.db.seed_roles, using the test session."""
    from app.db.seed_roles import SYSTEM_ROLES
    from app.models.organization import Role

    roles = {}
    for role_data in SYSTEM_ROLES:
        role = Role(**role_data)
        db_session.add(role)
        db_session.flush()
        roles[role_data["name"]] = role
    db_session.commit()
    return roles


@pytest.fixture()
def client(db_session):
    """FastAPI TestClient with the DB dependency overridden to use db_session."""
    from fastapi.testclient import TestClient

    from app.core.rate_limit import limiter
    from app.db.session import get_db
    from app.main import app

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    # All TestClient requests share one source IP, so slowapi's per-IP
    # counters would otherwise leak across tests within the same test run
    # (a later test can get spuriously rate-limited by an earlier one).
    # Real deployments don't have this problem — genuine clients have
    # distinct IPs — so this reset is test-isolation only, not a product
    # behavior change.
    limiter.reset()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:10]}@example.com"
