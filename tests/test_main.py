import random
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

TEST_EMPLOYEE_ID = 1
TEST_ATTENDANCE_DATE = date(2200, 1, 3)


def unique_future_date() -> str:
    return (date(2200, 1, 1) + timedelta(days=random.randint(0, 10000))).isoformat()


def get_token() -> str:
    response = client.post("/login")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["token_type"] == "bearer"
    assert payload["data"]["access_token"]
    return payload["data"]["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_login_returns_jwt_token():
    token = get_token()
    assert token


def test_endpoint_requires_jwt():
    response = client.get("/attendances")
    assert response.status_code == 401
    payload = response.json()
    assert payload["success"] is False
    assert "Authorization" in payload["message"]


def test_create_update_delete_attendance_flow():
    token = get_token()
    headers = auth_headers(token)

    attendance_payload = {
        "employee_id": TEST_EMPLOYEE_ID,
        "attendance_date": TEST_ATTENDANCE_DATE.isoformat(),
        "check_in": "08:00:00",
        "check_out": "17:00:00",
        "status": "Present",
        "notes": "Unit test attendance",
    }

    create_response = client.post("/attendances", json=attendance_payload, headers=headers)
    assert create_response.status_code == 201
    created = create_response.json()["data"]
    assert created["employee_name"] == "John Doe"
    assert created["attendance_date"] == TEST_ATTENDANCE_DATE.isoformat()
    attendance_id = created["id"]

    get_response = client.get(f"/attendances/{attendance_id}", headers=headers)
    assert get_response.status_code == 200
    got = get_response.json()["data"]
    assert got["status"] == "Present"
    assert got["employee_name"] == "John Doe"

    update_payload = attendance_payload.copy()
    update_payload["notes"] = "Updated by unit test"
    update_payload["check_out"] = "18:00:00"

    update_response = client.put(f"/attendances/{attendance_id}", json=update_payload, headers=headers)
    assert update_response.status_code == 200
    updated = update_response.json()["data"]
    assert updated["check_out"] == "18:00"

    delete_response = client.delete(f"/attendances/{attendance_id}", headers=headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["success"] is True

    get_after_delete = client.get(f"/attendances/{attendance_id}", headers=headers)
    assert get_after_delete.status_code == 404


def test_filter_by_employee_name():
    token = get_token()
    headers = auth_headers(token)

    response = client.get("/attendances?employee_name=John", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert isinstance(payload["data"]["items"], list)
    for item in payload["data"]["items"]:
        assert "john" in item["employee_name"].lower()


def test_filter_by_status_and_date():
    token = get_token()
    headers = auth_headers(token)

    response = client.get("/attendances?status=Present&date=2026-07-01", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["items"]
    for item in payload["data"]["items"]:
        assert item["status"] == "Present"
        assert item["attendance_date"] == "2026-07-01"


def test_sort_attendances_by_date_ascending():
    token = get_token()
    headers = auth_headers(token)

    response = client.get("/attendances?sort=asc&per_page=5", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    items = payload["data"]["items"]
    dates = [item["attendance_date"] for item in items]
    assert dates == sorted(dates)


def test_duplicate_attendance_is_rejected_on_create():
    token = get_token()
    headers = auth_headers(token)

    payload = {
        "employee_id": TEST_EMPLOYEE_ID,
        "attendance_date": unique_future_date(),
        "check_in": "08:00:00",
        "check_out": "17:00:00",
        "status": "Present",
        "notes": "Duplicate prevention check",
    }

    first_response = client.post("/attendances", json=payload, headers=headers)
    assert first_response.status_code == 201

    second_response = client.post("/attendances", json={**payload, "notes": "Attempted duplicate"}, headers=headers)
    assert second_response.status_code == 409
    assert second_response.json()["success"] is False

    list_response = client.get(f"/attendances?date={payload['attendance_date']}", headers=headers)
    assert list_response.status_code == 200
    items = list_response.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["notes"] == "Duplicate prevention check"


def test_recreate_soft_deleted_attendance():
    token = get_token()
    headers = auth_headers(token)

    attendance_date = unique_future_date()
    payload = {
        "employee_id": TEST_EMPLOYEE_ID,
        "attendance_date": attendance_date,
        "check_in": "08:00:00",
        "check_out": "17:00:00",
        "status": "Present",
        "notes": "Soft delete recreate check",
    }

    create_response = client.post("/attendances", json=payload, headers=headers)
    assert create_response.status_code == 201
    attendance_id = create_response.json()["data"]["id"]

    delete_response = client.delete(f"/attendances/{attendance_id}", headers=headers)
    assert delete_response.status_code == 200

    recreate_response = client.post("/attendances", json={**payload, "notes": "Recreated after delete"}, headers=headers)
    assert recreate_response.status_code == 201
    recreated = recreate_response.json()["data"]
    assert recreated["attendance_date"] == attendance_date
    assert recreated["employee_name"] == "John Doe"
