from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

try:
    from .database import get_db, initialize_database
except ImportError:
    from database import get_db, initialize_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
def read_root():
    return {"message": "Hello World!"}


@app.get("/db-check")
def test_db(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT version();")).fetchone()
    return {"status": "Koneksi DB Sukses", "version": result[0]}