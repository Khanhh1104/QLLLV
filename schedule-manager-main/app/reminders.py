"""Tạo thông báo bền vững và gửi email độc lập với trình duyệt.
Chạy: python -m app.reminders --loop ; hoặc cron: python -m app.reminders
"""

import argparse
import logging
import time
from datetime import timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from . import models, mailer
from .database import SessionLocal
from .timeutils import utcnow, aware_utc


def event_key(task):
    return f"{task.id}:{task.start_time.isoformat()}:{task.reminder_minutes}"


def generate(db, owner_id=None, now=None):
    now = now or utcnow()
    # Cho phép nhận nhắc trễ tối đa 24 giờ sau lúc bắt đầu nếu worker vừa khởi động lại.
    q = db.query(models.Task).filter(
        models.Task.deleted_at.is_(None),
        models.Task.status != models.TaskStatus.done,
        models.Task.reminder_minutes.isnot(None),
        models.Task.start_time >= now - timedelta(days=1),
        models.Task.start_time <= now + timedelta(days=7),
    )
    if owner_id is not None:
        q = q.filter(models.Task.owner_id == owner_id)
    created = 0
    for task in q.all():
        if task.start_time - timedelta(minutes=task.reminder_minutes) > now:
            continue
        key = event_key(task)
        if db.query(models.Notification.id).filter_by(event_key=key).first():
            continue
        try:
            with db.begin_nested():
                db.add(
                    models.Notification(
                        owner_id=task.owner_id,
                        task_id=task.id,
                        event_key=key,
                        title=f"Nhắc việc: {task.title}",
                    )
                )
                db.flush()
            created += 1
        except IntegrityError:
            pass
    db.commit()
    return created


def dispatch(db):
    created = generate(db)
    sent = 0
    if not mailer.configured():
        return {"created": created, "sent": 0, "email_configured": False}
    now = utcnow()
    stale = now - timedelta(minutes=5)
    q = (
        db.query(models.Notification)
        .join(models.User, models.User.id == models.Notification.owner_id)
        .join(models.Task, models.Task.id == models.Notification.task_id)
        .filter(
            models.Notification.email_sent_at.is_(None),
            models.Notification.email_attempts < 5,
            models.User.email_reminders.is_(True),
            models.Task.deleted_at.is_(None),
            models.Task.status != models.TaskStatus.done,
            models.Task.start_time >= now - timedelta(days=1),
            or_(
                models.Notification.email_claimed_at.is_(None),
                models.Notification.email_claimed_at < stale,
            ),
        )
    )
    for notice in q.limit(100).all():
        claimed = (
            db.query(models.Notification)
            .filter(
                models.Notification.id == notice.id,
                models.Notification.email_sent_at.is_(None),
                or_(
                    models.Notification.email_claimed_at.is_(None),
                    models.Notification.email_claimed_at < stale,
                ),
            )
            .update(
                {
                    "email_claimed_at": now,
                    "email_attempts": models.Notification.email_attempts + 1,
                },
                synchronize_session=False,
            )
        )
        db.commit()
        if not claimed:
            continue
        task = db.get(models.Task, notice.task_id)
        user = db.get(models.User, notice.owner_id)
        if not task or notice.event_key != event_key(task):
            continue
        local = (
            aware_utc(task.start_time)
            .astimezone(ZoneInfo(user.timezone))
            .strftime("%d/%m/%Y %H:%M")
        )
        try:
            mailer.send_mail(
                user.email,
                notice.title,
                f'{task.title}\nBắt đầu: {local} ({user.timezone})\n{task.description or ""}',
            )
            notice.email_sent_at = utcnow()
            db.commit()
            sent += 1
        except Exception:
            logging.exception("Không gửi được nhắc việc id=%s", notice.id)
            db.rollback()
    return {"created": created, "sent": sent, "email_configured": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()
    from .migrations import migrate

    migrate()
    while True:
        try:
            with SessionLocal() as db:
                print(dispatch(db), flush=True)
        except Exception:
            logging.exception("Lỗi xử lý nhắc việc")
        if not args.loop:
            break
        time.sleep(30)


if __name__ == "__main__":
    main()
