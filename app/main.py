import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .migrations import migrate
from . import mailer
from .routers import auth, tasks, stats, categories, notifications, transfer

_migration_lock = threading.Lock()
_migration_state = {"done": False, "error": None}


def ensure_migrated():
    """Tạo/nâng cấp bảng, chạy đúng một lần cho mỗi tiến trình.

    Trên serverless (Vercel) sự kiện lifespan không phải lúc nào cũng chạy, và
    mỗi lần "cold start" lại là một tiến trình mới, nên ta gọi hàm này ngay
    trước request đầu tiên thay vì chỉ lúc khởi động.
    """
    if _migration_state["done"]:
        return
    if os.getenv("AUTO_MIGRATE", "true").lower() != "true":
        _migration_state["done"] = True
        return
    with _migration_lock:
        if _migration_state["done"]:
            return
        try:
            migrate()
            _migration_state["error"] = None
        except Exception as exc:  # không làm sập cả app nếu DB lỗi
            _migration_state["error"] = f"{type(exc).__name__}: {exc}"
            return
        _migration_state["done"] = True


@asynccontextmanager
async def lifespan(app):
    ensure_migrated()
    yield


app = FastAPI(
    title="Lịch Làm Việc API",
    description="Quản lý lịch cá nhân, nhắc việc và thống kê",
    version="2.0.0",
    lifespan=lifespan,
)
origins = [s.strip() for s in os.getenv("CORS_ORIGINS", "").split(",") if s.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )


@app.middleware("http")
async def security_headers(request, call_next):
    ensure_migrated()
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path not in {"/docs", "/redoc", "/docs/oauth2-redirect"}:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
    if not request.url.path.endswith((".css", ".js")):
        response.headers["Cache-Control"] = "no-store"
    return response


for router in [
    auth.router,
    tasks.router,
    stats.router,
    categories.router,
    notifications.router,
    transfer.router,
]:
    app.include_router(router)


@app.get("/health")
def health():
    return {
        "status": "ok" if _migration_state["done"] else "degraded",
        "version": "2.0.0",
        "database_ready": _migration_state["done"],
        "database_error": _migration_state["error"],
    }


@app.get("/config")
def config():
    return {"email_configured": mailer.configured()}


app.mount(
    "/",
    StaticFiles(directory=Path(__file__).parent / "static", html=True),
    name="frontend",
)
