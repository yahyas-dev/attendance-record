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
    sql_file_path = os.path.join(os.path.dirname(__file__), "init.sql")

    if not os.path.exists(sql_file_path):
        print(f"File init.sql tidak ditemukan di path: {sql_file_path}")
        return

    print(" Menjalankan init.sql ke database...")
    try:
        with open(sql_file_path, "r", encoding="utf-8") as file:
            sql_script = file.read()

        with engine.begin() as connection:
            connection.exec_driver_sql(sql_script)

        print("Berhasil eksekusi init.sql!")
    except Exception as e:
        print(f"Gagal menjalankan init.sql: {e}")


def ensure_schema_migrations():
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE NULL;"
            )
            connection.exec_driver_sql(
                """
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conrelid = 'attendance'::regclass
                          AND conname = 'unique_employee_daily_attendance'
                    ) THEN
                        ALTER TABLE attendance DROP CONSTRAINT unique_employee_daily_attendance;
                    END IF;
                END
                $$;
                """
            )
            connection.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS unique_active_employee_daily_attendance ON attendance (employee_id, attendance_date) WHERE deleted_at IS NULL;"
            )
    except Exception as e:
        print(f"Gagal memastikan migrasi schema: {e}")


def initialize_database():
    Base.metadata.create_all(bind=engine)
    run_init_sql()
    ensure_schema_migrations()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
