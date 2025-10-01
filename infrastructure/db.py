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
    - Provide `init_db()` to create all tables based on metadata
    - Provide `get_session()` to obtain new AsyncSession objects
"""

import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase

# Load environment variables from a .env file (DB_DIR, etc.)
load_dotenv()

# Directory in which the SQLite file will live (default: "database")
DB_DIR = os.path.abspath(os.getenv("DB_DIR", "database"))

# Full SQLAlchemy URL for the async sqlite engine
DB_URL = f"sqlite+aiosqlite:///{DB_DIR}/database.db"


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


async def init_db() -> None:
    """
    Initialize the database by creating all tables defined in Base.metadata.

    This should be called once at startup to ensure all tables exist.

    Args:
        None

    Returns:
        None
    """
    async with engine.begin() as conn:
        # Run the create_all operation in the sync context
        await conn.run_sync(Base.metadata.create_all)
