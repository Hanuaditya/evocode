"""
backend/database.py

V2 upgrade: Reads DATABASE_URL from env so it works with both
SQLite (local dev: sqlite:///./evocode.db) and
Supabase Postgres (hosted demo: postgresql://...).
Falls back to SQLite if DATABASE_URL is not set.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

raw_url = os.getenv("DATABASE_URL", "")
if not raw_url or raw_url == "sqlite:///./evocode.db":
    db_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "evocode.db")).replace("\\", "/")
    DATABASE_URL = f"sqlite:///{db_file}"
else:
    DATABASE_URL = raw_url

# SQLite requires check_same_thread=False for FastAPI's threaded request handling
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def create_all_tables():
    """
    Creates all tables defined in models.py.
    Safe to call on every startup — SQLAlchemy is idempotent for existing tables.
    """
    import models  # noqa: F401 — registers all models with Base.metadata
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    FastAPI dependency that yields a fresh DB session per request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
