from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./evocode.db"

# connect_args={"check_same_thread": False} is required for SQLite in FastAPI/multithreaded environments
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative base class for models to inherit from
Base = declarative_base()

def create_all_tables():
    """
    Creates all tables in the database defined in models.py.
    """
    # Import models here to ensure they are registered with Base metadata before creation
    import models 
    Base.metadata.create_all(bind=engine)

def get_db():
    """
    Generator yielding a fresh database session for dependency injection.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
