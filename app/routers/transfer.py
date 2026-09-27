import csv
import io
from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo
from dateutil.rrule import rrulestr
from icalendar import Calendar, Event
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from .. import models, schemas, auth
from ..database import get_db
from ..services import check_conflicts
from ..timeutils import naive_utc, aware_utc, utcnow

router = APIRouter(prefix="/transfer", tags=["Nhập / xuất"])
MAX_SIZE = 2 * 1024 * 1024


def safe_csv(value):
    text = str(value or "")
    return (
        "'" + text
        if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r"))
        else text
    )


@router.get("/export")
def export(
    format: str = Query("ics", pattern="^(ics|csv)$"),
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    tasks = (
        db.query(models.Task)
        .filter_by(owner_id=user.id)
        .filter(models.Task.deleted_at.is_(None))
        .order_by(models.Task.start_time)
        .all()
    )
    if format == "csv":
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(
            [
                "title",
                "description",
                "category",
                "start_time",
                "end_time",
                "deadline",
                "status",
                "priority",
                "location",
                "meeting_url",
            ]
        )
        for task in tasks:
            writer.writerow(
                [
                    safe_csv(task.title),
                    safe_csv(task.description),
                    safe_csv(task.category),
                    aware_utc(task.start_time).isoformat(),
                    aware_utc(task.end_time).isoformat() if task.end_time else "",
                    aware_utc(task.deadline).isoformat() if task.deadline else "",
                    task.status.value,
                    task.priority.value,
                    safe_csv(task.location),
                    safe_csv(task.meeting_url),
                ]
            )
        content = ("\ufeff" + output.getvalue()).encode("utf-8")
        media = "text/csv; charset=utf-8"
    else:
        cal = Calendar()
        cal.add("prodid", "-//Schedule Manager//VI")
        cal.add("version", "2.0")
        for task in tasks:
            event = Event()
            event.add("uid", f"schedule-{user.id}-{task.id}@schedule-manager")
            event.add("dtstamp", aware_utc(utcnow()))
            event.add("dtstart", aware_utc(task.start_time))
            if task.end_time:
                event.add("dtend", aware_utc(task.end_time))
            event.add("summary", task.title)
            if task.description:
                event.add("description", task.description)
            if task.category:
                event.add("categories", [task.category])
            if task.location:
                event.add("location", task.location)
            if task.meeting_url:
                event.add("url", task.meeting_url)
            event.add("x-task-status", task.status.value)
            event.add("x-task-priority", task.priority.value)
            if task.deadline:
                event.add("x-task-deadline", aware_utc(task.deadline).isoformat())
            cal.add_component(event)
        content = cal.to_ical()
        media = "text/calendar; charset=utf-8"
    return Response(
        content,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="lich-lam-viec.{format}"'
        },
    )


def date_time(value, zone):
    if isinstance(value, datetime):
        return value.replace(tzinfo=zone) if value.tzinfo is None else value
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=zone)
    raise ValueError("Ngày giờ trong tệp không hợp lệ")


def read_ics(raw, user):
    cal = Calendar.from_ical(raw)
    zone = ZoneInfo(user.timezone)
    rows = []
    for event in cal.walk("VEVENT"):
        if event.get("recurrence-id") or event.get("rdate"):
            raise ValueError(
                "Tệp có ngoại lệ RECURRENCE-ID/RDATE. Hãy xuất các lần lặp thành sự kiện riêng trước khi nhập."
            )
        start = date_time(event.decoded("dtstart"), zone)
        end = (
            date_time(event.decoded("dtend"), zone)
            if event.get("dtend")
            else start + event.decoded("duration") if event.get("duration") else None
        )
        rule = event.get("rrule")
        occurrences = [start]
        series_id = None
        recurrence = "none"
        if rule:
            if not (rule.get("UNTIL") or rule.get("COUNT")):
                raise ValueError("Lịch lặp phải có COUNT hoặc UNTIL hữu hạn")
            freq = str(rule.get("FREQ", [""])[0])
            if freq not in {"DAILY", "WEEKLY", "MONTHLY"}:
                raise ValueError("Chỉ nhập lịch lặp theo ngày, tuần hoặc tháng")
            rule_text = rule.to_ical().decode()
            iterator = iter(rrulestr(rule_text, dtstart=start))
            occurrences = []
            for dt in iterator:
                if len(occurrences) >= 366 or (dt.date() - start.date()).days > 730:
                    raise ValueError("Tệp vượt giới hạn 366 lần lặp hoặc 2 năm")
                occurrences.append(dt)
            recurrence = {"DAILY": "daily", "WEEKLY": "weekly", "MONTHLY": "monthly"}[
                freq
            ]
            series_id = str(uuid4())
        excluded = set()
        exclusions = event.get("exdate", [])
        if not isinstance(exclusions, list):
            exclusions = [exclusions]
        for prop in exclusions:
            for item in prop.dts:
                excluded.add(naive_utc(date_time(item.dt, zone)))
        uid = str(event.get("uid", ""))
        category = None
        if event.get("categories"):
            props = event.get("categories")
            if isinstance(props, list):
                props = props[0]
            category = str(props.cats[0]) if props.cats else None
        for occurrence in occurrences:
            normalized = naive_utc(occurrence)
            if normalized in excluded:
                continue
            own_prefix = f"schedule-{user.id}-"
            source_id = None
            if uid.startswith(own_prefix) and uid.endswith("@schedule-manager"):
                try:
                    source_id = int(uid[len(own_prefix) :].split("@")[0])
                except ValueError:
                    pass
            deadline = event.get("x-task-deadline")
            rows.append(
                {
                    "title": str(event.get("summary", "Không có tiêu đề")),
                    "description": str(event.get("description", "")) or None,
                    "category": category,
                    "start_time": normalized,
                    "end_time": naive_utc(occurrence + (end - start)) if end else None,
                    "deadline": (
                        naive_utc(datetime.fromisoformat(str(deadline)))
                        + (normalized - naive_utc(start))
                        if deadline
                        else None
                    ),
                    "timezone": user.timezone,
                    "status": str(event.get("x-task-status", "todo")),
                    "priority": str(event.get("x-task-priority", "medium")),
                    "location": str(event.get("location", "")) or None,
                    "meeting_url": str(event.get("url", "")) or None,
                    "external_uid": (
                        (uid + ":" + normalized.isoformat()) if uid else None
                    ),
                    "series_id": series_id,
                    "recurrence": recurrence,
                    "recurrence_until": (
                        occurrences[-1].date().isoformat()
                        if rule and occurrences
                        else None
                    ),
                    "source_id": source_id,
                }
            )
            if len(rows) > 1000:
                raise ValueError("Mỗi lần nhập tối đa 1000 công việc")
    return rows


def read_csv(raw, user):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if not {"title", "start_time"}.issubset(set(reader.fieldnames or [])):
        raise ValueError("CSV cần cột title và start_time")
    rows = []
    for row in reader:
        item = {
            k: row.get(k) or None
            for k in [
                "title",
                "description",
                "category",
                "start_time",
                "end_time",
                "deadline",
                "location",
                "meeting_url",
            ]
        }
        item.update(
            status=row.get("status") or "todo",
            priority=row.get("priority") or "medium",
            timezone=user.timezone,
        )
        for key in ["title", "description", "category", "location", "meeting_url"]:
            if (
                item[key]
                and item[key].startswith("'")
                and item[key][1:].lstrip().startswith(("=", "+", "-", "@"))
            ):
                item[key] = item[key][1:]
        for key in ["start_time", "end_time", "deadline"]:
            if item[key]:
                item[key] = naive_utc(
                    date_time(
                        datetime.fromisoformat(item[key].replace("Z", "+00:00")),
                        ZoneInfo(user.timezone),
                    )
                )
        rows.append(item)
        if len(rows) > 1000:
            raise ValueError("Mỗi lần nhập tối đa 1000 công việc")
    return rows


@router.post("/import")
async def import_tasks(
    file: UploadFile = File(...),
    allow_overlap: bool = False,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    raw = await file.read(MAX_SIZE + 1)
    if len(raw) > MAX_SIZE:
        raise HTTPException(413, "Tệp tối đa 2 MB")
    name = (file.filename or "").lower()
    try:
        if name.endswith(".ics"):
            rows = read_ics(raw, user)
        elif name.endswith(".csv"):
            rows = read_csv(raw, user)
        else:
            raise ValueError("Chỉ hỗ trợ tệp .ics hoặc .csv")
        tasks = []
        skipped = 0
        seen = set()
        for row in rows:
            source_id = row.pop("source_id", None)
            uid = row.pop("external_uid", None)
            extra = {
                k: row.pop(k)
                for k in ["series_id", "recurrence", "recurrence_until"]
                if k in row
            }
            if (
                source_id
                and db.query(models.Task.id)
                .filter_by(owner_id=user.id, id=source_id)
                .first()
            ):
                skipped += 1
                continue
            if uid and (
                uid in seen
                or db.query(models.Task.id)
                .filter_by(owner_id=user.id, external_uid=uid)
                .first()
            ):
                skipped += 1
                continue
            if uid and len(uid) > 255:
                raise ValueError("UID sự kiện quá dài")
            if uid:
                seen.add(uid)
            data = schemas.TaskBase(**row)
            tasks.append(
                models.Task(
                    **data.model_dump(),
                    **extra,
                    owner_id=user.id,
                    external_uid=uid,
                    completed_at=None,
                )
            )
    except Exception as exc:
        raise HTTPException(422, f"Không thể nhập tệp: {str(exc)[:500]}")
    if not rows:
        raise HTTPException(422, "Tệp không có công việc nào")
    check_conflicts(db, user.id, tasks, allow_overlap)
    existing = {c.name for c in db.query(models.Category).filter_by(owner_id=user.id)}
    for task in tasks:
        if task.category and task.category not in existing:
            db.add(
                models.Category(owner_id=user.id, name=task.category, color="#4f7b69")
            )
            existing.add(task.category)
    db.add_all(tasks)
    db.commit()
    return {"imported": len(tasks), "skipped": skipped}
