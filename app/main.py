import os
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

load_dotenv()

try:
    from .database import get_db, initialize_database
except ImportError:
    from database import get_db, initialize_database


class AttendanceCreateRequest(BaseModel):
    employee_id: int
    attendance_date: date = Field(default_factory=date.today)
    check_in: Optional[time] = None
    check_out: Optional[time] = None
    status: str
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        allowed_status = {"Present", "Sick", "Leave", "Absent"}
        if value not in allowed_status:
            raise ValueError("status must be one of: Present, Sick, Leave, Absent")
        return value

    @model_validator(mode="after")
    def validate_times(self):
        if self.check_in and self.check_out and self.check_out < self.check_in:
            raise ValueError("check_out must be after check_in")
        if self.status == "Present" and self.check_in is None:
            raise ValueError("Present requires check_in")
        return self


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(lifespan=lifespan)


def get_jwt_settings():
    secret_key = os.getenv("JWT_SECRET_KEY")
    if not secret_key:
        raise RuntimeError("JWT_SECRET_KEY is not configured")

    algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    expires_minutes = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", "30"))
    return secret_key, algorithm, expires_minutes


def verify_token(token: str):
    secret_key, algorithm, _ = get_jwt_settings()
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.middleware("http")
async def jwt_middleware(request: Request, call_next):
    # Paths that do not require authentication
    exempt_paths = {"/", "/login", "/db-check", "/openapi.json", "/docs", "/redoc"}
    path = request.url.path

    if path in exempt_paths or path.startswith("/docs") or path.startswith("/openapi"):
        return await call_next(request)

    # Allow CORS preflight
    if request.method == "OPTIONS":
        return await call_next(request)

    auth = request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return error_response("Missing or invalid Authorization header", status_code=401)

    token = auth.split(" ", 1)[1]
    try:
        verify_token(token)
    except HTTPException as exc:
        return error_response(str(exc.detail), status_code=exc.status_code)

    return await call_next(request)


def format_time(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value[:5]
    return value.strftime("%H:%M")


def success_response(message: str, data=None):
    payload = {"success": True, "message": message}
    if data is not None:
        payload["data"] = data
    return payload


def error_response(message: str, errors=None, status_code: int = 400):
    payload = {"success": False, "message": message}
    if errors is not None:
        payload["errors"] = errors
    return JSONResponse(status_code=status_code, content=payload)


def normalize_status(status: Optional[str]) -> Optional[str]:
    if status is None:
        return None

    cleaned = status.strip()
    if not cleaned:
        return None

    mapping = {
        "present": "Present",
        "sick": "Sick",
        "leave": "Leave",
        "absent": "Absent",
    }
    return mapping.get(cleaned.lower(), cleaned)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = {}
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error.get("loc", []) if str(loc) != "body")
        field = field or "request"
        errors[field] = [error.get("msg", "Invalid value")]
    return error_response("Validation failed", errors, status_code=422)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        return error_response(detail.get("message", "Request failed"), detail.get("errors"), status_code=exc.status_code)
    return error_response(str(detail), None, status_code=exc.status_code)


@app.get("/")
def read_root():
    return {"message": "Hello World!"}


@app.get("/db-check")
def test_db(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT version();")).fetchone()
    return {"status": "Koneksi DB Sukses", "version": result[0]}


@app.post("/login")
def login():
    try:
        secret_key, algorithm, expires_minutes = get_jwt_settings()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    now = datetime.now(timezone.utc)
    expiration = now + timedelta(minutes=expires_minutes)
    token_payload = {
        "sub": "anonymous",
        "iat": int(now.timestamp()),
        "exp": int(expiration.timestamp()),
    }
    token = jwt.encode(token_payload, secret_key, algorithm=algorithm)

    return success_response(
        "Login successful",
        {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": expires_minutes * 60,
        },
    )


@app.post("/attendance", status_code=201)
def record_attendance(payload: AttendanceCreateRequest, db: Session = Depends(get_db)):
    employee = db.execute(
        text("SELECT id, name FROM employee WHERE id = :employee_id"),
        {"employee_id": payload.employee_id},
    ).fetchone()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    attendance_date = payload.attendance_date.strftime("%Y-%m-%d")
    check_in = payload.check_in.strftime("%H:%M:%S") if payload.check_in else None
    check_out = payload.check_out.strftime("%H:%M:%S") if payload.check_out else None

    duplicate = db.execute(
        text(
            """
            SELECT id
            FROM attendance
            WHERE employee_id = :employee_id
              AND attendance_date = :attendance_date
            """
        ),
        {"employee_id": payload.employee_id, "attendance_date": attendance_date},
    ).fetchone()

    if duplicate:
        raise HTTPException(status_code=409, detail="Attendance already exists for this employee and date. Use PUT to update it.")

    try:
        result = db.execute(
            text(
                """
                INSERT INTO attendance (
                    employee_id,
                    employee_name,
                    attendance_date,
                    check_in,
                    check_out,
                    status,
                    notes
                ) VALUES (
                    :employee_id,
                    :employee_name,
                    :attendance_date,
                    :check_in,
                    :check_out,
                    :status,
                    :notes
                )
                RETURNING id
                """
            ),
            {
                "employee_id": payload.employee_id,
                "employee_name": employee.name,
                "attendance_date": attendance_date,
                "check_in": check_in,
                "check_out": check_out,
                "status": payload.status,
                "notes": payload.notes,
            },
        ).fetchone()
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Attendance already exists for this employee and date. Use PUT to update it.") from exc

    return success_response(
        "Attendance created successfully",
        {
            "id": result[0],
            "employee_name": employee.name,
            "attendance_date": attendance_date,
            "check_in": format_time(payload.check_in),
            "check_out": format_time(payload.check_out),
            "status": payload.status,
        },
    )


@app.get("/attendances/filter")
def filter_attendances(
    db: Session = Depends(get_db),
    status: Optional[str] = Query(default=None),
    date: Optional[date] = Query(default=None),
    employee_name: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=10, ge=1, le=100),
):
    normalized_status = normalize_status(status)
    allowed_status = {"Present", "Sick", "Leave", "Absent"}
    if normalized_status is not None and normalized_status not in allowed_status:
        raise HTTPException(status_code=400, detail="status must be one of: Present, Sick, Leave, Absent")

    query_parts = ["SELECT a.id, a.employee_id, a.employee_name, a.attendance_date, a.check_in, a.check_out, a.status, a.notes, a.created_at, a.updated_at FROM attendance a WHERE 1=1 AND a.deleted_at IS NULL"]
    params = {}

    if normalized_status:
        query_parts.append("AND a.status = :status")
        params["status"] = normalized_status

    if date:
        query_parts.append("AND a.attendance_date = :attendance_date")
        params["attendance_date"] = date.strftime("%Y-%m-%d")

    if employee_name:
        query_parts.append("AND LOWER(a.employee_name) LIKE LOWER(:employee_name)")
        params["employee_name"] = f"%{employee_name}%"

    count_query = "SELECT COUNT(*) FROM attendance a WHERE 1=1 AND a.deleted_at IS NULL"
    if normalized_status:
        count_query += " AND a.status = :status"
    if date:
        count_query += " AND a.attendance_date = :attendance_date"
    if employee_name:
        count_query += " AND LOWER(a.employee_name) LIKE LOWER(:employee_name)"

    query_parts.append("ORDER BY a.attendance_date DESC, a.employee_id ASC")
    query_parts.append("LIMIT :limit OFFSET :offset")

    total_rows = db.execute(text(count_query), params).scalar_one()
    rows = db.execute(
        text(" ".join(query_parts)),
        {**params, "limit": per_page, "offset": (page - 1) * per_page},
    ).fetchall()

    attendances = []
    for row in rows:
        attendances.append(
            {
                "id": row.id,
                "employee_id": row.employee_id,
                "employee_name": row.employee_name,
                "attendance_date": str(row.attendance_date),
                "check_in": str(row.check_in) if row.check_in else None,
                "check_out": str(row.check_out) if row.check_out else None,
                "status": row.status,
                "notes": row.notes,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
        )

    total_pages = (total_rows + per_page - 1) // per_page if total_rows else 1

    return success_response(
        "Attendances filtered successfully",
        {
            "page": page,
            "per_page": per_page,
            "total_items": total_rows,
            "total_pages": total_pages,
            "items": attendances,
        },
    )


@app.get("/attendances")
def list_attendances(
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=10, ge=1, le=100),
):
    total_rows = db.execute(text("SELECT COUNT(*) FROM attendance WHERE deleted_at IS NULL")).scalar_one()

    rows = db.execute(
        text(
            """
            SELECT
                a.id,
                a.employee_id,
                a.employee_name,
                a.attendance_date,
                a.check_in,
                a.check_out,
                a.status,
                a.notes,
                a.created_at,
                a.updated_at
            FROM attendance a
            WHERE a.deleted_at IS NULL
            ORDER BY a.attendance_date DESC, a.employee_id ASC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"limit": per_page, "offset": (page - 1) * per_page},
    ).fetchall()

    attendances = []
    for row in rows:
        attendances.append(
            {
                "id": row.id,
                "employee_id": row.employee_id,
                "employee_name": row.employee_name,
                "attendance_date": str(row.attendance_date),
                "check_in": str(row.check_in) if row.check_in else None,
                "check_out": str(row.check_out) if row.check_out else None,
                "status": row.status,
                "notes": row.notes,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
        )

    total_pages = (total_rows + per_page - 1) // per_page if total_rows else 1

    return success_response(
        "Attendances retrieved successfully",
        {
            "page": page,
            "per_page": per_page,
            "total_items": total_rows,
            "total_pages": total_pages,
            "items": attendances,
        },
    )


@app.get("/attendance/{attendance_id}")
def get_attendance(attendance_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        text(
            """
            SELECT
                a.id,
                a.employee_id,
                a.employee_name,
                a.attendance_date,
                a.check_in,
                a.check_out,
                a.status,
                a.notes,
                a.created_at,
                a.updated_at
            FROM attendance a
            WHERE a.id = :attendance_id AND a.deleted_at IS NULL
            """
        ),
        {"attendance_id": attendance_id},
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Attendance not found")

    return success_response(
        "Attendance retrieved successfully",
        {
            "id": row.id,
            "employee_name": row.employee_name,
            "attendance_date": str(row.attendance_date),
            "check_in": format_time(row.check_in),
            "check_out": format_time(row.check_out),
            "status": row.status,
            "notes": row.notes,
        },
    )


@app.put("/attendances/{attendance_id}")
def update_attendance(attendance_id: int, payload: AttendanceCreateRequest, db: Session = Depends(get_db)):
    existing = db.execute(
        text("SELECT id FROM attendance WHERE id = :attendance_id AND deleted_at IS NULL"),
        {"attendance_id": attendance_id},
    ).fetchone()

    if not existing:
        raise HTTPException(status_code=404, detail="Attendance not found")

    employee = db.execute(
        text("SELECT id, name FROM employee WHERE id = :employee_id"),
        {"employee_id": payload.employee_id},
    ).fetchone()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    attendance_date = payload.attendance_date.strftime("%Y-%m-%d")
    check_in = payload.check_in.strftime("%H:%M:%S") if payload.check_in else None
    check_out = payload.check_out.strftime("%H:%M:%S") if payload.check_out else None

    db.execute(
        text(
            """
            UPDATE attendance
            SET
                employee_id = :employee_id,
                employee_name = :employee_name,
                attendance_date = :attendance_date,
                check_in = :check_in,
                check_out = :check_out,
                status = :status,
                notes = :notes,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :attendance_id
            """
        ),
        {
            "attendance_id": attendance_id,
            "employee_id": payload.employee_id,
            "employee_name": employee.name,
            "attendance_date": attendance_date,
            "check_in": check_in,
            "check_out": check_out,
            "status": payload.status,
            "notes": payload.notes,
        },
    )
    db.commit()

    return success_response(
        "Attendance updated successfully",
        {
            "id": attendance_id,
            "employee_name": employee.name,
            "attendance_date": attendance_date,
            "check_in": format_time(payload.check_in),
            "check_out": format_time(payload.check_out),
            "status": payload.status,
        },
    )


@app.delete("/attendances/{attendance_id}")
def delete_attendance(attendance_id: int, db: Session = Depends(get_db)):
    existing = db.execute(
        text("SELECT id FROM attendance WHERE id = :attendance_id AND deleted_at IS NULL"),
        {"attendance_id": attendance_id},
    ).fetchone()

    if not existing:
        raise HTTPException(status_code=404, detail="Attendance not found")

    db.execute(
        text("UPDATE attendance SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = :attendance_id"),
        {"attendance_id": attendance_id},
    )
    db.commit()

    return success_response("Attendance deleted successfully", {"id": attendance_id})