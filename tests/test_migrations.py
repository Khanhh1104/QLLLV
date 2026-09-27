from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from app import migrations, models


def test_upgrade_v1_preserves_data(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///" + str(tmp_path / "legacy.db"))
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(50) NOT NULL UNIQUE, email VARCHAR(120) NOT NULL UNIQUE, hashed_password VARCHAR(255) NOT NULL, created_at DATETIME)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE tasks (id INTEGER PRIMARY KEY, title VARCHAR(200) NOT NULL, description TEXT, category VARCHAR(50), start_time DATETIME NOT NULL, end_time DATETIME, status VARCHAR(11) NOT NULL, priority VARCHAR(6) NOT NULL, created_at DATETIME, updated_at DATETIME, owner_id INTEGER NOT NULL)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO users VALUES (1,'legacy','legacy@example.com','hash','2026-01-01 00:00:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO tasks VALUES (1,'Bài tập cũ','Giữ nguyên nội dung','Học tập','2026-09-01 02:00:00','2026-09-01 03:00:00','done','high','2026-01-01 00:00:00','2026-01-01 00:00:00',1)"
            )
        )
    monkeypatch.setattr(migrations, "engine", engine)
    monkeypatch.setattr(migrations, "SessionLocal", sessionmaker(bind=engine))
    migrations.migrate()
    migrations.migrate()
    inspector = inspect(engine)
    task_columns = {column["name"] for column in inspector.get_columns("tasks")}
    assert {"location", "meeting_url", "actual_minutes", "timer_started_at"} <= task_columns
    assert {"task_templates", "saved_filters", "activity_logs"} <= set(
        inspector.get_table_names()
    )
    with sessionmaker(bind=engine)() as db:
        user = db.get(models.User, 1)
        task = db.get(models.Task, 1)
        assert user.username == "legacy" and user.timezone == "Asia/Ho_Chi_Minh"
        assert task.title == "Bài tập cũ" and task.checklist == []
        assert task.completed_at is None  # Không bịa thời điểm hoàn thành dữ liệu cũ.
        assert task.start_time.hour == 2
        assert db.query(models.Category).count() == 1
    engine.dispose()
