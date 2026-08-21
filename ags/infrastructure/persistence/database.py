from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def normalize_database_url(url: str) -> str:
    """Normalize PostgreSQL URLs to the psycopg 3 SQLAlchemy dialect."""

    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]

    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]

    return url


class Database:
    def __init__(self, url: str) -> None:
        self.url = normalize_database_url(url)
        if self.url.startswith("sqlite:///"):
            path = self.url[len("sqlite:///") :]
            if path and path != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
        connect_args = {"check_same_thread": False} if self.url.startswith("sqlite") else {}
        self.engine = create_engine(self.url, future=True, pool_pre_ping=True, connect_args=connect_args)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)
