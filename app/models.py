import enum
from .timeutils import utcnow
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Enum,
    ForeignKey,
    Text,
    Boolean,
    JSON,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from .database import Base


class TaskStatus(str, enum.Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"


class TaskPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=utcnow)
    display_name = Column(String(100), nullable=True)
    timezone = Column(String(80), nullable=False, default="Asia/Ho_Chi_Minh")
    email_reminders = Column(Boolean, nullable=False, default=False)
    token_version = Column(Integer, nullable=False, default=0)
    tasks = relationship("Task", back_populates="owner", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(String(50))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    deadline = Column(DateTime)
    status = Column(Enum(TaskStatus), default=TaskStatus.todo, nullable=False)
    priority = Column(Enum(TaskPriority), default=TaskPriority.medium, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    completed_at = Column(DateTime)
    deleted_at = Column(DateTime)
    series_id = Column(String(36), index=True)
    recurrence = Column(String(10), default="none", nullable=False)
    recurrence_until = Column(String(10))
    timezone = Column(String(80), default="Asia/Ho_Chi_Minh", nullable=False)
    reminder_minutes = Column(Integer)
    checklist = Column(JSON, default=list, nullable=False)
    external_uid = Column(String(255))
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    owner = relationship("User", back_populates="tasks")
    __table_args__ = (Index("ix_task_owner_start", "owner_id", "start_time"),)


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    color = Column(String(7), nullable=False, default="#4f7b69")
    __table_args__ = (UniqueConstraint("owner_id", "name"),)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    task_id = Column(
        Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    event_key = Column(String(160), unique=True, nullable=False)
    title = Column(String(240), nullable=False)
    created_at = Column(DateTime, default=utcnow)
    read_at = Column(DateTime)
    email_sent_at = Column(DateTime)
    email_claimed_at = Column(DateTime)
    email_attempts = Column(Integer, default=0, nullable=False)


class PasswordReset(Base):
    __tablename__ = "password_resets"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime)


class AuthAttempt(Base):
    __tablename__ = "auth_attempts"
    id = Column(Integer, primary_key=True)
    key = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
