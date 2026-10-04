from datetime import datetime, timedelta, timezone
import re
from unittest.mock import Mock
import pytest
from app import models, mailer
from app.reminders import generate, dispatch
from app.timeutils import utcnow


def payload(**kw):
    return {
        "title": "Họp dự án",
        "start_time": "2026-10-05T09:00:00+07:00",
        "end_time": "2026-10-05T10:00:00+07:00",
        **kw,
    }


def create(client, **kw):
    response = client.post("/tasks", json=payload(**kw))
    assert response.status_code == 201, response.text
    return response.json()


def test_crud_timezone_completed_and_trash(logged):
    task = create(logged, checklist=[{"text": "Chuẩn bị", "done": False}])
    assert task["start_time"] == "2026-10-05T02:00:00Z"
    assert task["checklist"][0]["text"] == "Chuẩn bị"
    response = logged.put(f'/tasks/{task["id"]}', json={"status": "done"})
    assert response.json()["completed_at"].endswith("Z")
    assert logged.get("/stats").json()["done"] == 1
    assert logged.delete(f'/tasks/{task["id"]}').status_code == 204
    assert logged.get("/tasks").json()["total"] == 0
    assert logged.get("/stats").json()["total"] == 0
    assert logged.get("/tasks?trash=true").json()["total"] == 1
    assert logged.post(f'/tasks/{task["id"]}/restore').status_code == 200
    logged.delete(f'/tasks/{task["id"]}')
    assert logged.delete(f'/tasks/{task["id"]}/permanent').status_code == 204
    assert logged.get("/tasks?trash=true").json()["total"] == 0


def test_owner_isolation(logged):
    task = create(logged)
    logged.post(
        "/auth/register",
        json={
            "username": "other",
            "email": "other@example.com",
            "password": "password123",
        },
    )
    token = logged.post(
        "/auth/login", data={"username": "other", "password": "password123"}
    ).json()["access_token"]
    logged.headers["Authorization"] = "Bearer " + token
    assert logged.get("/tasks").json()["total"] == 0
    assert logged.get("/stats").json()["total"] == 0
    for method, url, kw in [
        ("get", f'/tasks/{task["id"]}', {}),
        ("put", f'/tasks/{task["id"]}', {"json": {"title": "stolen"}}),
        ("delete", f'/tasks/{task["id"]}', {}),
        ("post", f'/tasks/{task["id"]}/restore', {}),
    ]:
        assert getattr(logged, method)(url, **kw).status_code == 404


@pytest.mark.parametrize(
    "changes",
    [
        {"title": "  "},
        {"title": "a" * 201},
        {"end_time": "2026-10-05T08:00:00+07:00"},
        {"deadline": "2026-10-04T00:00:00Z"},
        {"reminder_minutes": -1},
        {"checklist": [{"text": "  "}]},
        {"timezone": "Invalid/Zone"},
    ],
)
def test_validation(logged, changes):
    assert logged.post("/tasks", json=payload(**changes)).status_code == 422


def test_conflict_confirmation_and_adjacent(logged):
    first = create(logged)
    conflict = logged.post("/tasks", json=payload(title="Việc trùng"))
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["conflicts"][0]["id"] == first["id"]
    create(logged, title="Cho phép trùng", allow_overlap=True)
    adjacent = create(
        logged,
        start_time="2026-10-05T10:00:00+07:00",
        end_time="2026-10-05T11:00:00+07:00",
    )
    assert (
        logged.put(
            f'/tasks/{adjacent["id"]}', json={"start_time": "2026-10-05T09:30:00+07:00"}
        ).status_code
        == 409
    )
    assert (
        logged.get(f'/tasks/{adjacent["id"]}').json()["start_time"]
        == "2026-10-05T03:00:00Z"
    )


def test_recurring_one_and_series(logged):
    first = create(logged, recurrence="weekly", recurrence_until="2026-10-26")
    tasks = logged.get("/tasks").json()["items"]
    assert len(tasks) == 4
    second = tasks[1]
    assert (
        logged.put(
            f'/tasks/{second["id"]}', json={"title": "Riêng lần này"}
        ).status_code
        == 200
    )
    assert logged.get(f'/tasks/{first["id"]}').json()["title"] == "Họp dự án"
    response = logged.put(
        f'/tasks/{second["id"]}',
        json={
            "title": "Cả chuỗi",
            "start_time": "2026-10-12T11:00:00+07:00",
            "end_time": "2026-10-12T12:00:00+07:00",
            "scope": "series",
        },
    )
    assert response.status_code == 200, response.text
    tasks = logged.get("/tasks").json()["items"]
    assert len(tasks) == 4 and all(t["title"] == "Cả chuỗi" for t in tasks)
    assert all(t["start_time"][11:16] == "04:00" for t in tasks)
    assert logged.delete(f'/tasks/{first["id"]}?scope=series').status_code == 204
    assert logged.get("/tasks?trash=true").json()["total"] == 4


def test_recurrence_limits_monthly_and_dst(logged):
    bad = logged.post("/tasks", json=payload(recurrence="daily"))
    assert bad.status_code == 422
    assert (
        logged.post(
            "/tasks", json=payload(recurrence="daily", recurrence_until="2028-12-31")
        ).status_code
        == 422
    )
    create(
        logged,
        start_time="2026-01-31T09:00:00+07:00",
        end_time=None,
        recurrence="monthly",
        recurrence_until="2026-05-31",
    )
    assert [t["start_time"][5:10] for t in logged.get("/tasks").json()["items"]] == [
        "01-31",
        "03-31",
        "05-31",
    ]
    create(
        logged,
        title="DST",
        start_time="2026-03-01T09:00:00-05:00",
        end_time="2026-03-01T10:00:00-05:00",
        timezone="America/New_York",
        recurrence="weekly",
        recurrence_until="2026-03-15",
    )
    times = [t["start_time"] for t in logged.get("/tasks?keyword=DST").json()["items"]]
    assert times == [
        "2026-03-01T14:00:00Z",
        "2026-03-08T13:00:00Z",
        "2026-03-15T13:00:00Z",
    ]


def test_category_rename_delete_and_owner(logged):
    category = logged.post(
        "/categories", json={"name": "Dự án", "color": "#aa5522"}
    ).json()
    task = create(logged, category="Dự án")
    logged.put(
        "/categories/" + str(category["id"]),
        json={"name": "Dự án mới", "color": "#2255aa"},
    )
    assert logged.get("/tasks/" + str(task["id"])).json()["category"] == "Dự án mới"
    assert logged.post("/categories", json={"name": "Dự án mới"}).status_code == 409
    assert logged.delete("/categories/" + str(category["id"])).status_code == 204
    assert logged.get("/tasks/" + str(task["id"])).json()["category"] is None
    assert (
        logged.post("/tasks", json=payload(category="Không tồn tại")).status_code == 422
    )


def test_pagination_filters_stats(logged, session):
    for i in range(4):
        create(
            logged,
            title=f"Việc {i}",
            start_time=f"2026-10-0{i+5}T09:00:00+07:00",
            end_time=f"2026-10-0{i+5}T10:00:00+07:00",
            priority="high" if i == 0 else "low",
        )
    page = logged.get("/tasks?page=2&page_size=2").json()
    assert page["total"] == 4 and len(page["items"]) == 2
    assert logged.get("/tasks?priority=high").json()["total"] == 1
    assert (
        logged.get(
            "/tasks?date_from=2026-10-05T17:00:00Z&date_to=2026-10-06T17:00:00Z"
        ).json()["total"]
        == 1
    )
    assert logged.get("/tasks?keyword=%25").json()["total"] == 0
    task = session.query(models.Task).first()
    task.status = models.TaskStatus.done
    task.completed_at = datetime(2026, 10, 5, 2, 30)
    session.commit()
    data = logged.get("/stats?date_from=2026-10-05&date_to=2026-10-08").json()
    assert data["period"]["completion_rate"] == 25
    assert data["period"]["completed"] == 1 and data["period"]["on_time"] == 1
    assert (
        logged.get("/stats?date_from=2026-10-10&date_to=2026-10-01").status_code == 422
    )


def test_reminders_deduplicate_read_email(logged, session, monkeypatch):
    now = utcnow()
    task = create(
        logged,
        start_time=(now + timedelta(minutes=10))
        .replace(tzinfo=timezone.utc)
        .isoformat(),
        end_time=None,
        reminder_minutes=15,
    )
    assert generate(session) == 1
    assert generate(session) == 0
    notices = logged.get("/notifications").json()
    assert notices["unread"] == 1
    logged.post(f'/notifications/{notices["items"][0]["id"]}/read')
    assert logged.get("/notifications").json()["unread"] == 0
    account = session.query(models.User).first()
    account.email_reminders = True
    session.commit()
    sender = Mock()
    monkeypatch.setattr(mailer, "configured", lambda: True)
    monkeypatch.setattr(mailer, "send_mail", sender)
    assert dispatch(session)["sent"] == 1
    assert dispatch(session)["sent"] == 0
    assert sender.call_count == 1
    logged.put("/tasks/" + str(task["id"]), json={"status": "done"})
    assert logged.get("/notifications").json()["total"] == 0


def test_cron_auth(logged, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "secret-for-cron")
    assert logged.post("/internal/reminders").status_code == 401
    assert (
        logged.post(
            "/internal/reminders", headers={"Authorization": "Bearer secret-for-cron"}
        ).status_code
        == 200
    )


def test_profile_password_revokes_tokens(logged):
    response = logged.put(
        "/auth/me",
        json={
            "display_name": "Khánh",
            "email": "new@example.com",
            "timezone": "UTC",
            "email_reminders": True,
        },
    )
    assert response.status_code == 200
    assert logged.get("/auth/me").json()["display_name"] == "Khánh"
    assert (
        logged.post(
            "/auth/change-password",
            json={"current_password": "wrong", "new_password": "nextPassword"},
        ).status_code
        == 400
    )
    assert (
        logged.post(
            "/auth/change-password",
            json={"current_password": "password123", "new_password": "nextPassword"},
        ).status_code
        == 200
    )
    assert logged.get("/auth/me").status_code == 401
    assert (
        logged.post(
            "/auth/login", data={"username": "khanh", "password": "nextPassword"}
        ).status_code
        == 200
    )


def test_reset_token_single_use(logged, monkeypatch):
    sender = Mock()
    monkeypatch.setattr(mailer, "configured", lambda: True)
    monkeypatch.setattr(mailer, "send_mail", sender)
    assert (
        logged.post(
            "/auth/forgot-password", json={"email": "khanh@example.com"}
        ).status_code
        == 200
    )
    message = sender.call_args.args[2]
    token = re.search(r"#reset=([^\s]+)", message).group(1)
    assert (
        logged.post(
            "/auth/reset-password",
            json={"token": token, "new_password": "newPassword123"},
        ).status_code
        == 200
    )
    assert (
        logged.post(
            "/auth/reset-password",
            json={"token": token, "new_password": "newPassword456"},
        ).status_code
        == 400
    )
    assert logged.get("/auth/me").status_code == 401


def test_ics_csv_roundtrip_and_atomic_import(logged):
    task = create(
        logged,
        title="Báo cáo, học tập",
        description="Dòng một\nDòng hai",
        category="Học tập",
        location="Phòng A1",
        meeting_url="https://meet.example.com/roundtrip",
    )
    ics = logged.get("/transfer/export?format=ics")
    assert ics.status_code == 200 and b"VCALENDAR" in ics.content
    result = logged.post(
        "/transfer/import", files={"file": ("test.ics", ics.content, "text/calendar")}
    )
    assert result.status_code == 200, result.text
    assert result.json() == {"imported": 0, "skipped": 1}
    csv = logged.get("/transfer/export?format=csv")
    assert csv.content.startswith(b"\xef\xbb\xbf")
    conflict = logged.post(
        "/transfer/import", files={"file": ("test.csv", csv.content, "text/csv")}
    )
    assert conflict.status_code == 409
    assert logged.get("/tasks").json()["total"] == 1
    result = logged.post(
        "/transfer/import?allow_overlap=true",
        files={"file": ("test.csv", csv.content, "text/csv")},
    )
    assert result.status_code == 200 and result.json()["imported"] == 1
    assert logged.get("/tasks").json()["total"] == 2
    copies = logged.get("/tasks?keyword=Báo%20cáo").json()["items"]
    assert all(item["location"] == "Phòng A1" for item in copies)
    assert all(
        item["meeting_url"] == "https://meet.example.com/roundtrip"
        for item in copies
    )
    bad = b"title,start_time,end_time\nGood,2027-01-01T09:00:00Z,2027-01-01T10:00:00Z\nBad,invalid,\n"
    assert (
        logged.post("/transfer/import", files={"file": ("bad.csv", bad)}).status_code
        == 422
    )
    assert logged.get("/tasks").json()["total"] == 2


def test_ics_recurrence_import_and_duplicate(logged):
    raw = b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:external123\r\nDTSTART:20261201T020000Z\r\nDTEND:20261201T030000Z\r\nSUMMARY:Weekly\r\nRRULE:FREQ=WEEKLY;COUNT=3\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    result = logged.post("/transfer/import", files={"file": ("repeat.ics", raw)})
    assert result.status_code == 200, result.text
    assert result.json()["imported"] == 3
    again = logged.post("/transfer/import", files={"file": ("repeat.ics", raw)})
    assert again.json()["skipped"] == 3
    bad = raw.replace(b"COUNT=3", b"COUNT=10000")
    assert (
        logged.post("/transfer/import", files={"file": ("repeat.ics", bad)}).status_code
        == 422
    )


def test_restore_conflict(logged):
    task = create(logged)
    logged.delete("/tasks/" + str(task["id"]))
    create(logged, title="Khác")
    assert logged.post(f'/tasks/{task["id"]}/restore').status_code == 409
    assert logged.get("/tasks?trash=true").json()["total"] == 1
    assert (
        logged.post(f'/tasks/{task["id"]}/restore?allow_overlap=true').status_code
        == 200
    )


def test_update_validation_and_conflict_at_point(logged):
    point = create(logged, start_time="2026-10-05T09:00:00Z", end_time=None)
    assert (
        logged.post(
            "/tasks",
            json=payload(
                start_time="2026-10-05T09:00:30Z", end_time="2026-10-05T09:30:00Z"
            ),
        ).status_code
        == 409
    )
    assert (
        logged.put(
            "/tasks/" + str(point["id"]), json={"timezone": "NoSuchZone"}
        ).status_code
        == 422
    )
    for changes in [
        {"title": "  "},
        {"start_time": None},
        {"reminder_minutes": -1},
        {"checklist": None},
        {"status": None},
    ]:
        assert logged.put("/tasks/" + str(point["id"]), json=changes).status_code == 422


def test_half_open_day_and_upcoming_filters(logged):
    create(
        logged,
        start_time="2026-10-05T23:00:00+07:00",
        end_time="2026-10-06T00:00:00+07:00",
    )
    assert (
        logged.get(
            "/tasks?date_from=2026-10-05T17:00:00Z&date_to=2026-10-06T17:00:00Z"
        ).json()["total"]
        == 0
    )
    create(
        logged,
        title="Có hạn chót",
        start_time="2026-10-07T09:00:00+07:00",
        end_time=None,
        deadline="2026-10-08T09:00:00+07:00",
    )
    upcoming = logged.get(
        "/tasks?unfinished=true&due_from=2026-10-08T00:00:00Z&due_to=2026-10-09T00:00:00Z"
    ).json()
    assert upcoming["total"] == 1 and upcoming["items"][0]["title"] == "Có hạn chót"
