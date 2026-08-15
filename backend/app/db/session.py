"""
SQLAlchemy engine + session factory.

Uses the classic sync engine for now (simplest, most compatible with Alembic).
Can be swapped for the async engine later without touching model code.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# pool_size / max_overflow are Postgres (QueuePool) specific and are not
# accepted by SQLite's pool implementations. Tests run against an in-memory
# SQLite DB (see app/tests/conftest.py), so these kwargs are only passed
# when the configured database is actually Postgres — this keeps a single
# session module correct for both without any test-only branching in
# application code.
_engine_kwargs = {"pool_pre_ping": True}
if settings.DATABASE_URL.startswith("postgresql"):
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20

engine = create_engine(settings.DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency that yields a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
