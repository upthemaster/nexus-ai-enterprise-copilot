"""
SQLite database engine and session configuration using SQLAlchemy.

Why: Table 4 and Table 11 of the Blueprint require relational storage for document records,
ingestion status, and conversation metadata for the MVP.
"""

import logging
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session

from app.core.config import settings

logger = logging.getLogger("nexusai.db")

Base = declarative_base()

# Create SQLite engine with multithreading support for FastAPI
engine = create_engine(
    settings.sqlite_db_url,
    connect_args={"check_same_thread": False},
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(custom_engine=None) -> None:
    """
    Initialize database schema by creating all registered tables.
    """
    target_engine = custom_engine or engine
    logger.info("Initializing SQLite database tables at: %s", target_engine.url)
    Base.metadata.create_all(bind=target_engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a thread-local database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

