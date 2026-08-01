import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def initialize_database():
    """Membuat skema dan memuat data awal secara idempotent."""
    Base.metadata.create_all(bind=engine)
    run_init_sql()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
