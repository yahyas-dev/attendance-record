import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def run_init_sql():
    """Membaca dan menjalankan file init.sql ke PostgreSQL."""
    sql_file_path = os.path.join(os.path.dirname(__file__), "init.sql")

    if not os.path.exists(sql_file_path):
        print(f"⚠️ File init.sql tidak ditemukan di path: {sql_file_path}")
        return

    print("🚀 Menjalankan init.sql ke database...")
    try:
        with open(sql_file_path, "r", encoding="utf-8") as file:
            sql_script = file.read()

        with engine.begin() as connection:
            connection.exec_driver_sql(sql_script)

        print("✅ Berhasil eksekusi init.sql!")
    except Exception as e:
        print(f"❌ Gagal menjalankan init.sql: {e}")


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
