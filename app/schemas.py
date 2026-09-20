from datetime import datetime, date
from typing import Optional, Literal
from pydantic import (
    BaseModel,
    EmailStr,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from .models import TaskStatus, TaskPriority
from .timeutils import naive_utc, aware_utc, valid_zone


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: EmailStr = Field(max_length=120)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def password_bytes(cls, v):
        if len(v.encode()) > 72:
            raise ValueError("Mật khẩu tối đa 72 byte UTF-8")
        return v


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: EmailStr
    display_name: Optional[str] = None
    timezone: str
    email_reminders: bool
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def utc(cls, v):
        return aware_utc(v)


class ProfileUpdate(BaseModel):
    display_name: str = Field(max_length=100)
    email: EmailStr = Field(max_length=120)
    timezone: str = "Asia/Ho_Chi_Minh"
    email_reminders: bool = False

    @field_validator("timezone")
    @classmethod
    def zone(cls, v):
        return valid_zone(v)


class ChangePassword(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: str = Field(min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def password_bytes(cls, v):
        return UserCreate.password_bytes(v)


class ForgotPassword(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def password_bytes(cls, v):
        return UserCreate.password_bytes(v)


class ChecklistItem(BaseModel):
    text: str = Field(min_length=1, max_length=200)
    done: bool = False

    @field_validator("text")
    @classmethod
    def nonblank(cls, v):
        if not v.strip():
            raise ValueError("Nội dung không được để trống")
        return v.strip()


class TaskBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=10000)
    category: Optional[str] = Field(None, max_length=50)
    start_time: datetime
    end_time: Optional[datetime] = None
    deadline: Optional[datetime] = None
    status: TaskStatus = TaskStatus.todo
    priority: TaskPriority = TaskPriority.medium
    timezone: str = "Asia/Ho_Chi_Minh"
    reminder_minutes: Optional[int] = Field(None, ge=0, le=10080)
    checklist: list[ChecklistItem] = Field(default_factory=list, max_length=100)

    @field_validator("title")
    @classmethod
    def title_required(cls, v):
        if not v.strip():
            raise ValueError("Tiêu đề không được để trống")
        return v.strip()

    @field_validator("category")
    @classmethod
    def trim_category(cls, v):
        return (v.strip() or None) if v else None

    @field_validator("timezone")
    @classmethod
    def zone(cls, v):
        return valid_zone(v)

    @field_validator("start_time", "end_time", "deadline")
    @classmethod
    def normalize_time(cls, v):
        return naive_utc(v)

    @model_validator(mode="after")
    def valid_range(self):
        if self.end_time is not None and self.end_time <= self.start_time:
            raise ValueError("Giờ kết thúc phải sau giờ bắt đầu")
        if self.deadline is not None and self.deadline < self.start_time:
            raise ValueError("Hạn chót phải từ giờ bắt đầu trở đi")
        return self


class TaskCreate(TaskBase):
    recurrence: Literal["none", "daily", "weekly", "monthly"] = "none"
    recurrence_until: Optional[date] = None
    allow_overlap: bool = False


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    deadline: Optional[datetime] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    timezone: Optional[str] = None
    reminder_minutes: Optional[int] = None
    checklist: Optional[list[ChecklistItem]] = None
    scope: Literal["one", "series"] = "one"
    allow_overlap: bool = False


class TaskOut(TaskBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner_id: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    series_id: Optional[str] = None
    recurrence: str
    recurrence_until: Optional[str] = None

    @field_validator(
        "start_time",
        "end_time",
        "deadline",
        "created_at",
        "updated_at",
        "completed_at",
        "deleted_at",
        mode="after",
    )
    @classmethod
    def output_utc(cls, v):
        return aware_utc(v)


class TaskPage(BaseModel):
    items: list[TaskOut]
    total: int
    page: int
    page_size: int


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    color: str = Field(default="#4f7b69", pattern=r"^#[0-9a-fA-F]{6}$")

    @field_validator("name")
    @classmethod
    def trim(cls, v):
        if not v.strip():
            raise ValueError("Tên danh mục không được trống")
        return v.strip()


class CategoryOut(CategoryIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int
    title: str
    created_at: datetime
    read_at: Optional[datetime]

    @field_validator("created_at", "read_at")
    @classmethod
    def utc(cls, v):
        return aware_utc(v)
