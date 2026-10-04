"""Khởi tạo môi trường local bằng Python 3.11+ (khuyến nghị 3.12)."""

import os
from pathlib import Path
import secrets
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
if sys.version_info < (3, 11):
    raise SystemExit("Cần Python 3.11 trở lên, khuyến nghị Python 3.12.")
if not (ROOT / ".env").exists():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    text = text.replace(
        "replace-this-with-your-own-random-secret-at-least-32-characters",
        secrets.token_urlsafe(48),
    )
    text = text.replace("CRON_SECRET=", "CRON_SECRET=" + secrets.token_urlsafe(32))
    (ROOT / ".env").write_text(text, encoding="utf-8")
    print("Đã tạo .env với khóa riêng.")
if not (ROOT / ".venv").exists():
    print("Đang tạo môi trường Python…")
    venv.create(ROOT / ".venv", with_pip=True)
python = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
subprocess.run(
    [str(python), "-m", "pip", "install", "-r", "requirements.txt"], check=True
)
subprocess.run([str(python), "-m", "app.migrations"], check=True)
print("Sẵn sàng. Windows: chạy start.bat và reminders.bat ở hai cửa sổ riêng.")
print(
    "Hoặc chạy: "
    + str(python)
    + " -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
)
