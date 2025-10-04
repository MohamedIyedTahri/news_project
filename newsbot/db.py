"""Database configuration helpers for the Newsbot project.

This module encapsulates engine creation and session management so that the
application can transparently switch between a local SQLite database (useful
for development and testing) and the production PostgreSQL deployment running
inside Docker.  Configuration is driven by environment variables to keep
runtime environments fully declarative.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Dict, Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

_DEFAULT_SQLITE_PATH = os.environ.get("NEWSBOT_SQLITE_PATH", "news_articles.db")
_ENV_KEY = "NEWSBOT_ENV"
_CACHE: Dict[str, sessionmaker] = {}

_POOL_KWARGS = {
    "pool_size": int(os.environ.get("DB_POOL_SIZE", "5")),
    "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW", "10")),
    "pool_timeout": int(os.environ.get("DB_POOL_TIMEOUT", "30")),
    "pool_pre_ping": True,
}


def _build_database_url(env: str | None = None) -> str:
    env = (env or os.environ.get(_ENV_KEY, "DEV")).upper()
    explicit_url = os.environ.get("DATABASE_URL")
    if explicit_url:
        return explicit_url

    if env == "PROD":
        host = os.environ.get("POSTGRES_HOST", "postgres")
        port = os.environ.get("POSTGRES_PORT", "5432")
        user = os.environ.get("POSTGRES_USER", "newsbot")
        password = os.environ.get("POSTGRES_PASSWORD", "newsbot")
        database = os.environ.get("POSTGRES_DB", "newsbot")
        return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"

    # Development fallback to SQLite for convenience
    sqlite_path = os.path.abspath(_DEFAULT_SQLITE_PATH)
    return f"sqlite:///{sqlite_path}"


def _create_engine(database_url: str) -> Engine:
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        engine = create_engine(
            database_url,
            echo=False,
            future=True,
            connect_args=connect_args,
        )
    else:
        engine = create_engine(
            database_url,
            echo=False,
            future=True,
            **_POOL_KWARGS,
        )
    return engine


def get_session_factory(database_url: Optional[str] = None) -> sessionmaker:
    """Return (and cache) a configured ``sessionmaker`` instance."""

    url = database_url or _build_database_url()
    if url in _CACHE:
        return _CACHE[url]

    engine = _create_engine(url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)
    _CACHE[url] = factory
    return factory


@contextmanager
def session_scope(database_url: Optional[str] = None) -> Generator[Session, None, None]:
    """Provide a transactional scope for a series of operations."""

    factory = get_session_factory(database_url)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:  # pragma: no cover - defensive safety net
        session.rollback()
        raise
    finally:
        session.close()


__all__ = ["get_session_factory", "session_scope"]
