from datetime import timedelta, timezone

from app import models
from app.reminders import generate
from app.timeutils import utcnow



def create(client, **changes):
    data = {
        "title": "Họp dự án",
        "start_time": "2026-10-05T09:00:00+07:00",
        "end_time": "2026-10-05T10:00:00+07:00",
        **changes,
    }
    response = client.post("/tasks", json=data)
    assert response.status_code == 201, response.text
    return response.json()


def test_task_location_meeting_link_and_validation(logged):
    task = create(
        logged,
        location="Phòng A1",
        meeting_url="https://meet.example.com/abc",
    )
    assert task["location"] == "Phòng A1"
    assert task["meeting_url"] == "https://meet.example.com/abc"
    assert logged.put(
        f'/tasks/{task["id"]}', json={"meeting_url": "javascript:alert(1)"}
    ).status_code == 422


def test_templates_crud_and_owner_isolation(logged):
    body = {
        "name": "Họp tuần",
        "title": "Họp nhóm",
        "description": "Chuẩn bị báo cáo",
        "priority": "high",
        "duration_minutes": 45,
        "reminder_minutes": 15,
        "checklist": [{"text": "Mở tài liệu", "done": False}],
        "location": "Phòng họp",
        "meeting_url": "https://meet.example.com/team",
    }
    response = logged.post("/templates", json=body)
    assert response.status_code == 201, response.text
    template = response.json()
    assert template["duration_minutes"] == 45
    assert logged.post("/templates", json=body).status_code == 409
    body["title"] = "Họp cập nhật"
    assert logged.put(f'/templates/{template["id"]}', json=body).json()["title"] == "Họp cập nhật"

    logged.post(
        "/auth/register",
        json={
            "username": "template_other",
            "email": "template_other@example.com",
            "password": "password123",
        },
    )
    token = logged.post(
        "/auth/login",
        data={"username": "template_other", "password": "password123"},
    ).json()["access_token"]
    logged.headers["Authorization"] = "Bearer " + token
    assert logged.get("/templates").json() == []
    assert logged.delete(f'/templates/{template["id"]}').status_code == 404


def test_saved_filters_are_sanitized(logged):
    response = logged.post(
        "/saved-filters",
        json={
            "name": "Việc gấp",
            "query": {
                "priority": "high",
                "overdue": True,
                "unknown": "không lưu",
                "keyword": "",
            },
        },
    )
    assert response.status_code == 201
    item = response.json()
    assert item["query"] == {"priority": "high", "overdue": True}
    assert logged.post(
        "/saved-filters", json={"name": "Việc gấp", "query": {}}
    ).status_code == 409
    assert logged.delete(f'/saved-filters/{item["id"]}').status_code == 204


def test_duplicate_reschedule_timer_and_activity(logged, session):
    original = create(logged, checklist=[{"text": "Chuẩn bị", "done": True}])
    duplicate = logged.post(
        f'/tasks/{original["id"]}/duplicate',
        json={"offset_days": 1, "allow_overlap": False},
    )
    assert duplicate.status_code == 201, duplicate.text
    copied = duplicate.json()
    assert copied["title"].endswith("(bản sao)")
    assert copied["start_time"].startswith("2026-10-06")
    assert copied["checklist"][0]["done"] is False

    moved = logged.post(
        f'/tasks/{original["id"]}/reschedule',
        json={"target_date": "2026-10-07"},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["start_time"].startswith("2026-10-07")

    started = logged.post(f'/tasks/{original["id"]}/timer/start')
    assert started.status_code == 200
    assert logged.get("/timers/active").json()["id"] == original["id"]
    assert logged.post(f'/tasks/{copied["id"]}/timer/start').status_code == 409
    row = session.get(models.Task, original["id"])
    row.timer_started_at = utcnow() - timedelta(minutes=31)
    session.commit()
    stopped = logged.post(f'/tasks/{original["id"]}/timer/stop')
    assert stopped.status_code == 200
    assert stopped.json()["actual_minutes"] >= 31
    assert logged.get("/timers/active").json() is None

    actions = {item["action"] for item in logged.get("/activities").json()["items"]}
    assert {"created", "duplicated", "rescheduled", "timer_started", "timer_stopped"} <= actions


def test_snooze_hides_unread_until_later(logged, session):
    now = utcnow()
    create(
        logged,
        start_time=(now + timedelta(minutes=10))
        .replace(tzinfo=timezone.utc)
        .isoformat(),
        end_time=None,
        reminder_minutes=15,
    )
    assert generate(session) == 1
    before = logged.get("/notifications").json()
    notice = before["items"][0]
    assert before["unread"] == 1
    response = logged.post(
        f'/notifications/{notice["id"]}/snooze', json={"minutes": 10}
    )
    assert response.status_code == 200
    after = logged.get("/notifications").json()
    assert after["unread"] == 0
    assert after["items"][0]["snoozed_until"] is not None


def test_pdf_report(logged):
    create(logged, title="Báo cáo tiếng Việt", location="Văn phòng")
    response = logged.get(
        "/reports/tasks.pdf?date_from=2026-10-01&date_to=2026-10-31"
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert "bao-cao-lich-2026-10-01-2026-10-31.pdf" in response.headers[
        "content-disposition"
    ]
    assert response.content.startswith(b"%PDF-") and len(response.content) > 2000
    assert logged.get(
        "/reports/tasks.pdf?date_from=2025-01-01&date_to=2026-12-31"
    ).status_code == 422
