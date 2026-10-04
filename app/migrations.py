"""Nâng cấp bổ sung schema v1 -> v2; không xóa bảng/dữ liệu cũ.
Chạy một tiến trình migration trước khi khởi động nhiều worker.
"""

from sqlalchemy import inspect, text
from .database import engine, Base, SessionLocal
from . import models

ADDITIONS = {
    "users": {
        "display_name": "VARCHAR(100)",
        "timezone": "VARCHAR(80) NOT NULL DEFAULT 'Asia/Ho_Chi_Minh'",
        "email_reminders": "BOOLEAN NOT NULL DEFAULT FALSE",
        "token_version": "INTEGER NOT NULL DEFAULT 0",
    },
    "tasks": {
        "deadline": "TIMESTAMP",
        "completed_at": "TIMESTAMP",
        "deleted_at": "TIMESTAMP",
        "series_id": "VARCHAR(36)",
        "recurrence": "VARCHAR(10) NOT NULL DEFAULT 'none'",
        "recurrence_until": "VARCHAR(10)",
        "timezone": "VARCHAR(80) NOT NULL DEFAULT 'Asia/Ho_Chi_Minh'",
        "reminder_minutes": "INTEGER",
        "checklist": "JSON NOT NULL DEFAULT '[]'",
        "external_uid": "VARCHAR(255)",
        "location": "VARCHAR(300)",
        "meeting_url": "VARCHAR(2048)",
        "actual_minutes": "INTEGER NOT NULL DEFAULT 0",
        "timer_started_at": "TIMESTAMP",
    },
    "notifications": {"snoozed_until": "TIMESTAMP"},
}


def migrate():
    with engine.begin() as conn:
        inspector = inspect(conn)
        for table, columns in ADDITIONS.items():
            if inspector.has_table(table):
                existing = {c["name"] for c in inspector.get_columns(table)}
                for name, sql_type in columns.items():
                    if name not in existing:
                        conn.execute(
                            text(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}")
                        )
    Base.metadata.create_all(bind=engine)
    for table in Base.metadata.tables.values():
        for index in table.indexes:
            index.create(bind=engine, checkfirst=True)
    with SessionLocal() as db:
        existing = {(c.owner_id, c.name) for c in db.query(models.Category).all()}
        for owner_id, name in db.query(
            models.Task.owner_id, models.Task.category
        ).distinct():
            if name and (owner_id, name) not in existing:
                db.add(models.Category(owner_id=owner_id, name=name, color="#4f7b69"))
                existing.add((owner_id, name))
        db.commit()


if __name__ == "__main__":
    migrate()
    print("Đã nâng cấp cơ sở dữ liệu.")
