from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

TEST_EMPLOYEE_ID = 1
TEST_ATTENDANCE_DATE = date(2099, 12, 31)


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

    create_response = client.post("/attendance", json=attendance_payload, headers=headers)
    assert create_response.status_code == 201
    created = create_response.json()["data"]
    assert created["employee_name"] == "John Doe"
    assert created["attendance_date"] == TEST_ATTENDANCE_DATE.isoformat()
    attendance_id = created["id"]

    get_response = client.get(f"/attendance/{attendance_id}", headers=headers)
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

    get_after_delete = client.get(f"/attendance/{attendance_id}", headers=headers)
    assert get_after_delete.status_code == 404


def test_filter_by_employee_name():
    token = get_token()
    headers = auth_headers(token)

    response = client.get("/attendances/filter?employee_name=John", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert isinstance(payload["data"]["items"], list)
    for item in payload["data"]["items"]:
        assert "john" in item["employee_name"].lower()
