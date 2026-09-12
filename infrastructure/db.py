"""
SQLAlchemy Database Setup
=========================

Module path:
    src/infrastructure/db.py

Summary:
    Initializes the async SQLAlchemy engine, session factory, and database file location.

Responsibilities:
    - Load environment variables for DB_DIR from .env
    - Compute the SQLite database URL (DB_URL)
    - Define the Declarative Base class for ORM models
    - Create an async engine bound to the SQLite URL
    - Expose SessionLocal factory for creating AsyncSession instances
    - Provide init_db() to apply pending Alembic migrations
    - Provide `get_session()` to obtain new AsyncSession objects
"""

import os
import asyncio
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase

# Load environment variables from a .env file (DB_DIR, etc.)
load_dotenv()

# Directory in which the SQLite file will live (default: "database")
DB_DIR = os.path.abspath(os.getenv("DB_DIR", "database"))
os.makedirs(DB_DIR, exist_ok=True)

# Full SQLAlchemy URL for the async sqlite engine
DB_URL = f"sqlite+aiosqlite:///{DB_DIR}/database.db"

# Used to adopt a database created before Alembic was introduced, without re-running its schema.
BASELINE_REVISION = "96f7e0807499"

# Sync twin of DB_URL, for Alembic's bookkeeping and inspection.
DB_URL_SYNC = DB_URL.replace("+aiosqlite", "")


class Base(DeclarativeBase):
    """
    Base class for all ORM models.
    All model classes should inherit from this to register metadata.
    """
    pass


# Create the async engine using the computed DB_URL
engine = create_async_engine(DB_URL, future=True)

# SessionLocal factory: produces AsyncSession, with expire_on_commit=False
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

def _migrate_sync() -> None:
    """
    Bring the database to the latest schema revision.

    Handles four states:
      - fresh database           -> run every migration from the baseline
      - pre-Alembic database     -> stamp the baseline, then upgrade
      - empty alembic_version    -> stamp the baseline, then upgrade
      - Alembic-managed database -> upgrade (no-op when already current)
    """

    cfg = Config("alembic.ini")

    probe = create_engine(DB_URL_SYNC)
    try:
        insp       = inspect(probe)
        adopted    = insp.has_table("alembic_version")
        has_schema = insp.has_table("submissions")

        current_rev = None
        if adopted:
            with probe.connect() as conn:
                current_rev = conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar()
    finally:
        probe.dispose()

    needs_stamp = (has_schema and not adopted) or (adopted and current_rev is None)
    if needs_stamp:
        # Existing database whose schema predates Alembic (or whose
        # version table is empty).
        command.stamp(cfg, BASELINE_REVISION)

    command.upgrade(cfg, "head")



async def init_db() -> None:
    """
    Make sure the database is up to the latest alembic version.

    Called once at startup.

    Args:
        None

    Returns:
        None
    """
    await asyncio.to_thread(_migrate_sync)
