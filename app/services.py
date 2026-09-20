from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from uuid import uuid4
from itertools import islice
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY
from fastapi import HTTPException
from sqlalchemy import func
from . import models, schemas
from .timeutils import naive_utc, aware_utc, utcnow

FIELDS = list(schemas.TaskBase.model_fields)


def task_data(task):
    return {field: getattr(task, field) for field in FIELDS}


def owned(db, task_id, owner_id, deleted=False):
    q = db.query(models.Task).filter(
        models.Task.id == task_id, models.Task.owner_id == owner_id
    )
    q = q.filter(
        models.Task.deleted_at.isnot(None)
        if deleted
        else models.Task.deleted_at.is_(None)
    )
    task = q.first()
    if not task:
        raise HTTPException(404, "Không tìm thấy công việc")
    return task


def validate_category(db, owner_id, name):
    if (
        name
        and not db.query(models.Category)
        .filter_by(owner_id=owner_id, name=name)
        .first()
    ):
        raise HTTPException(422, "Danh mục không tồn tại. Hãy tạo danh mục trước.")


def recurring_tasks(data, owner_id):
    base = data.model_dump(exclude={"recurrence", "recurrence_until", "allow_overlap"})
    if data.recurrence == "none":
        return [
            models.Task(
                **base,
                owner_id=owner_id,
                recurrence="none",
                completed_at=(
                    utcnow() if data.status == models.TaskStatus.done else None
                ),
            )
        ]
    zone = ZoneInfo(data.timezone)
    local_start = aware_utc(data.start_time).astimezone(zone)
    if not data.recurrence_until or data.recurrence_until < local_start.date():
        raise HTTPException(422, "Lịch lặp cần ngày kết thúc từ ngày bắt đầu trở đi")
    if (data.recurrence_until - local_start.date()).days > 730:
        raise HTTPException(422, "Ngày kết thúc lặp tối đa 2 năm kể từ ngày bắt đầu")
    until = datetime.combine(data.recurrence_until, time.max, tzinfo=zone)
    dates = list(
        islice(
            rrule(
                {"daily": DAILY, "weekly": WEEKLY, "monthly": MONTHLY}[data.recurrence],
                dtstart=local_start,
                until=until,
            ),
            367,
        )
    )
    if len(dates) > 366:
        raise HTTPException(422, "Tối đa 366 lần lặp. Hãy rút ngắn khoảng thời gian.")
    series_id = str(uuid4())
    items = []
    for occurrence in dates:
        shift = occurrence.replace(tzinfo=None) - local_start.replace(tzinfo=None)
        values = dict(base)
        for field in ["start_time", "end_time", "deadline"]:
            if base[field] is not None:
                values[field] = naive_utc(
                    aware_utc(base[field]).astimezone(zone) + shift
                )
        # Mỗi lần lặp có checklist và trạng thái độc lập.
        values["checklist"] = [dict(x) for x in base["checklist"]]
        items.append(
            models.Task(
                **values,
                owner_id=owner_id,
                series_id=series_id,
                recurrence=data.recurrence,
                recurrence_until=data.recurrence_until.isoformat(),
                completed_at=(
                    utcnow() if data.status == models.TaskStatus.done else None
                ),
            )
        )
    return items


def conflicts(db, owner_id, candidates, exclude_ids=()):
    active = [c for c in candidates if c.status != models.TaskStatus.done]
    if not active:
        return []
    first = min(c.start_time for c in active)
    last = max(c.end_time or c.start_time + timedelta(minutes=1) for c in active)
    q = db.query(models.Task).filter(
        models.Task.owner_id == owner_id,
        models.Task.deleted_at.is_(None),
        models.Task.status != models.TaskStatus.done,
        models.Task.start_time < last,
        func.coalesce(models.Task.end_time, models.Task.start_time)
        >= first - timedelta(minutes=1),
    )
    if exclude_ids:
        q = q.filter(models.Task.id.notin_(exclude_ids))
    rows = q.all()
    found = {}
    for candidate in active:
        end = candidate.end_time or candidate.start_time + timedelta(minutes=1)
        for other in rows:
            other_end = other.end_time or other.start_time + timedelta(minutes=1)
            if candidate.start_time < other_end and other.start_time < end:
                key = other.id or f"{other.title}:{other.start_time}"
                found[key] = {
                    "id": other.id,
                    "title": other.title,
                    "start_time": aware_utc(other.start_time).isoformat(),
                    "end_time": (
                        aware_utc(other.end_time).isoformat()
                        if other.end_time
                        else None
                    ),
                }
        rows.append(candidate)
        if len(found) >= 20:
            break
    return list(found.values())[:20]


def check_conflicts(db, owner_id, candidates, allow_overlap=False, exclude_ids=()):
    if allow_overlap:
        return
    found = conflicts(db, owner_id, candidates, exclude_ids)
    if found:
        raise HTTPException(
            409,
            detail={
                "message": "Khoảng thời gian trùng với công việc khác. Bạn vẫn muốn lưu?",
                "conflicts": found,
            },
        )


def clear_reminders(db, ids):
    db.query(models.Notification).filter(models.Notification.task_id.in_(ids)).delete(
        synchronize_session=False
    )
