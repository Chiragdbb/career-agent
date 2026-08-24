from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings

_engine = None
_SessionLocal = None


def init_db(settings: Settings | None = None) -> None:
    """Create the SQLAlchemy engine and session factory."""
    global _engine, _SessionLocal

    settings = settings or get_settings()
    _engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
    )
    _SessionLocal = sessionmaker(
        bind=_engine,
        autocommit=False,
        autoflush=False,
        class_=Session,
    )


def get_engine():
    if _engine is None:
        init_db()
    return _engine


def get_session_factory():
    if _SessionLocal is None:
        init_db()
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session."""
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
