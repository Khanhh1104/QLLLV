import io
import os
import unicodedata
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .timeutils import aware_utc, utcnow


def _font_candidates():
    custom = os.getenv("PDF_FONT_PATH")
    if custom:
        yield Path(custom)
    yield Path(__file__).parent / "assets" / "DejaVuSans.ttf"
    yield Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    yield Path("/usr/share/fonts/dejavu/DejaVuSans.ttf")


def _font_setup():
    for path in _font_candidates():
        if path.exists():
            bold = path.with_name("DejaVuSans-Bold.ttf")
            pdfmetrics.registerFont(TTFont("ScheduleSans", str(path)))
            pdfmetrics.registerFont(
                TTFont("ScheduleSansBold", str(bold if bold.exists() else path))
            )
            return "ScheduleSans", "ScheduleSansBold", True
    # Hạ cấp an toàn nếu runtime không có font Unicode: vẫn tạo PDF đọc được.
    return "Helvetica", "Helvetica-Bold", False


def _text(value, unicode_ready):
    value = str(value or "")
    if unicode_ready:
        return value
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()


def build_tasks_pdf(tasks, user, period_from: date, period_to: date):
    normal, bold, unicode_ready = _font_setup()
    zone = ZoneInfo(user.timezone)
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=15 * mm,
        bottomMargin=14 * mm,
        title=_text("Báo cáo lịch làm việc", unicode_ready),
        author=_text(user.display_name or user.username, unicode_ready),
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "ScheduleTitle",
        parent=styles["Title"],
        fontName=bold,
        fontSize=20,
        leading=25,
        textColor=colors.HexColor("#243E33"),
        alignment=TA_CENTER,
    )
    body = ParagraphStyle(
        "ScheduleBody", parent=styles["BodyText"], fontName=normal, fontSize=8.5
    )
    small = ParagraphStyle(
        "ScheduleSmall",
        parent=body,
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#52635B"),
    )
    done = sum(task.status.value == "done" for task in tasks)
    overdue = sum(
        task.status.value != "done"
        and (task.deadline or task.end_time)
        and (task.deadline or task.end_time) < utcnow()
        for task in tasks
    )
    minutes = sum(task.actual_minutes or 0 for task in tasks)
    story = [
        Paragraph(_text("BÁO CÁO LỊCH LÀM VIỆC", unicode_ready), title),
        Spacer(1, 4 * mm),
        Paragraph(
            _text(
                f"Người dùng: {user.display_name or user.username} | "
                f"Thời gian: {period_from.strftime('%d/%m/%Y')} - {period_to.strftime('%d/%m/%Y')} | "
                f"Múi giờ: {user.timezone}",
                unicode_ready,
            ),
            small,
        ),
        Spacer(1, 5 * mm),
    ]
    summary = Table(
        [
            [
                _text("Tổng công việc", unicode_ready),
                _text("Hoàn thành", unicode_ready),
                _text("Quá hạn", unicode_ready),
                _text("Thời gian thực tế", unicode_ready),
            ],
            [str(len(tasks)), str(done), str(overdue), f"{minutes // 60}h {minutes % 60}m"],
        ],
        colWidths=[62 * mm] * 4,
    )
    summary.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF0E5")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#243E33")),
                ("FONTNAME", (0, 0), (-1, 0), bold),
                ("FONTNAME", (0, 1), (-1, -1), normal),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D7DED2")),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([summary, Spacer(1, 7 * mm)])
    rows = [
        [
            _text("Công việc", unicode_ready),
            _text("Bắt đầu", unicode_ready),
            _text("Kết thúc/Hạn", unicode_ready),
            _text("Danh mục", unicode_ready),
            _text("Trạng thái", unicode_ready),
            _text("Ưu tiên", unicode_ready),
            _text("Thực tế", unicode_ready),
        ]
    ]
    status_labels = {"todo": "Chưa làm", "in_progress": "Đang làm", "done": "Hoàn thành"}
    priority_labels = {"low": "Thấp", "medium": "Trung bình", "high": "Cao"}
    for task in tasks:
        start = aware_utc(task.start_time).astimezone(zone)
        end = task.deadline or task.end_time
        end_text = aware_utc(end).astimezone(zone).strftime("%d/%m/%Y %H:%M") if end else "-"
        rows.append(
            [
                Paragraph(_text(task.title, unicode_ready), body),
                start.strftime("%d/%m/%Y %H:%M"),
                end_text,
                Paragraph(_text(task.category or "Chưa phân loại", unicode_ready), body),
                _text(status_labels[task.status.value], unicode_ready),
                _text(priority_labels[task.priority.value], unicode_ready),
                f"{(task.actual_minutes or 0) // 60}h {(task.actual_minutes or 0) % 60}m",
            ]
        )
    table = Table(
        rows,
        repeatRows=1,
        colWidths=[60 * mm, 35 * mm, 37 * mm, 34 * mm, 28 * mm, 24 * mm, 27 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#243E33")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), bold),
                ("FONTNAME", (0, 1), (-1, -1), normal),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D7DED2")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F8F3")]),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(table)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(normal, 7.5)
        canvas.setFillColor(colors.HexColor("#7B877F"))
        canvas.drawString(14 * mm, 8 * mm, _text("Lịch Làm Việc", unicode_ready))
        canvas.drawRightString(
            landscape(A4)[0] - 14 * mm,
            8 * mm,
            _text(f"Trang {doc.page}", unicode_ready),
        )
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
