from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
import os
from dotenv import load_dotenv
from calendar import monthcalendar
from datetime import datetime, timedelta, timezone, date
from werkzeug.security import check_password_hash


load_dotenv()

# ✅ เวลาไทย (UTC+7) ใช้ที่เดียวทั้งแอป ไม่ขึ้นกับ timezone ของเซิร์ฟเวอร์
THAI_TZ = timezone(timedelta(hours=7))


def thai_now():
    return datetime.now(THAI_TZ)


def thai_today():
    return thai_now().strftime("%Y-%m-%d")


THAI_MONTHS_FULL = ["", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
                    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
THAI_MONTHS_SHORT = ["", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
                     "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
THAI_DAYS = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]


def _to_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])

# ✅ ดึงค่าจาก Environment Variables (Render จะตั้งให้)
DATABASE_URL = os.getenv("DATABASE_URL")
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")


@app.template_filter("thaidate")
def thaidate_filter(value, short=True):
    """2026-10-20 -> 20 ต.ค. 2569 (short) หรือ 20 ตุลาคม 2569"""
    try:
        d = _to_date(value)
    except Exception:
        return value
    months = THAI_MONTHS_SHORT if short else THAI_MONTHS_FULL
    return f"{d.day} {months[d.month]} {d.year + 543}"


@app.template_filter("thaiday")
def thaiday_filter(value):
    try:
        return THAI_DAYS[_to_date(value).weekday()]
    except Exception:
        return ""


@app.template_filter("daysleft")
def daysleft_filter(value, today=None):
    """จำนวนวันที่เหลือจนถึงกำหนดส่ง (ติดลบ = เลยกำหนด)"""
    try:
        base = _to_date(today) if today else thai_now().date()
        return (_to_date(value) - base).days
    except Exception:
        return None


@app.context_processor
def inject_globals():
    return {"today": thai_now().date(), "room_name": "ห้อง 4/15"}

@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

@app.route("/")
def index():
    """หน้าแรกสาธารณะ = ปฏิทินการบ้าน (ไม่ต้องล็อกอิน)"""
    return shared_calendar()


@app.route("/dashboard")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    today = thai_today()

    cur.execute("""
        SELECT announcements.*, 
            subjects.subject_name, 
            subjects.teacher_name
        FROM announcements
        JOIN subjects ON announcements.subject_id = subjects.id
        WHERE announce_date = %s
        ORDER BY due_date ASC
    """, (today,))
    
    announcements = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("dashboard.html", announcements=announcements)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET" and "user_id" in session:
        return redirect(url_for("home"))
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            return redirect(url_for("home"))
        else:
            return render_template("login.html", error="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"), 401

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))



@app.route("/add", methods=["GET", "POST"])
def add():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    if request.method == "POST":
        type_value = request.form["type"]
        subject_id = request.form["subject_id"]
        detail = request.form["detail"]
        
        now_thailand = thai_now()
        announce_date = now_thailand.strftime("%Y-%m-%d")
        due_date = request.form["due_date"]

        cur.execute("""
            INSERT INTO announcements
            (type, subject_id, detail, announce_date, due_date, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (type_value, subject_id, detail, announce_date, due_date, now_thailand))

        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for("home"))

    cur.execute("SELECT * FROM subjects ORDER BY id ASC")
    subjects = cur.fetchall()
    cur.close()
    conn.close()
    
    return render_template("add.html", subjects=subjects)

@app.route("/send")
def send():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    today = thai_today()

    cur.execute("""
        SELECT announcements.*, 
               subjects.subject_name, 
               subjects.teacher_name
        FROM announcements
        JOIN subjects ON announcements.subject_id = subjects.id
        WHERE announce_date = %s
        ORDER BY due_date ASC
    """, (today,))
    
    rows = cur.fetchall()
    cur.close()
    conn.close()

    message_text = format_line_message(rows)

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }

    if len(message_text) > 4900:
        message_text = message_text[:4900] + "\n\n(ข้อความถูกตัดบางส่วน)"

    data = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": message_text}]
    }

    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        return render_template("send_success.html")
    else:
        return render_template("send_error.html", error=response.text)
    
    
@app.route("/health")
def health():
    """ใช้โดย Docker healthcheck / Cloudflare ตรวจว่าแอปและฐานข้อมูลยังทำงาน"""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return {"status": "ok"}, 200
    except Exception as e:
        return {"status": "error", "detail": str(e)}, 500


def _split_subject(name):
    """'คณิตศาสตร์ (ค31224)' -> ('คณิตศาสตร์', 'ค31224'); ชื่อที่ไม่มีวงเล็บคืนรหัสว่าง"""
    name = (name or "").strip()
    if name.endswith(")") and "(" in name:
        base, code = name.rsplit("(", 1)
        return base.strip(), code[:-1].strip()
    return name, ""


def _announcement_dict(row, today):
    subject, code = _split_subject(row["subject_name"])
    due = _to_date(row["due_date"])
    return {
        "id": row["id"],
        "type": row["type"],
        "subject": subject,
        "code": code,
        "teacher": row["teacher_name"],
        "detail": row["detail"],
        "announce_date": str(_to_date(row["announce_date"])),
        "due_date": str(due),
        "days_left": (due - today).days,
    }


@app.route("/api/today")
def api_today():
    """JSON อ่านอย่างเดียวสำหรับจอทีวีในห้องเรียน: งานที่ครบกำหนดส่งวันนี้ และงานที่จะถึงใน 7 วัน
    ไม่ต้องล็อกอิน (ข้อมูลชุดเดียวกับปฏิทินสาธารณะ) ใช้เวลาไทยเสมอ"""
    now = thai_now()
    today = now.date()
    horizon = today + timedelta(days=7)

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT announcements.*, subjects.subject_name, subjects.teacher_name
        FROM announcements
        JOIN subjects ON announcements.subject_id = subjects.id
        WHERE due_date BETWEEN %s AND %s
        ORDER BY due_date ASC, announcements.id ASC
    """, (today, horizon))
    rows = [_announcement_dict(r, today) for r in cur.fetchall()]
    cur.close()
    conn.close()

    due_today = [r for r in rows if r["days_left"] == 0]
    upcoming = [r for r in rows if r["days_left"] > 0]
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "date": str(today),
        "room": "ห้อง 4/15",
        "today": due_today,
        "tomorrow_count": sum(1 for r in upcoming if r["days_left"] == 1),
        "upcoming": upcoming[:10],
    }


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print(data)
    return "OK"

@app.route("/history")
def history():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT announce_date, COUNT(*) as total
        FROM announcements
        GROUP BY announce_date
        ORDER BY announce_date DESC
    """)
    
    summary = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("history.html", summary=summary)

@app.route("/history/<date>")
def history_detail(date):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT announcements.*, 
               subjects.subject_name, 
               subjects.teacher_name
        FROM announcements
        JOIN subjects ON announcements.subject_id = subjects.id
        WHERE announce_date = %s
        ORDER BY due_date ASC
    """, (date,))
    
    announcements = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("history_detail.html", announcements=announcements, date=date)

@app.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM announcements WHERE id = %s", (id,))
    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("home"))

@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    if request.method == "POST":
        type_value = request.form["type"]
        subject_id = request.form["subject_id"]
        detail = request.form["detail"]
        due_date = request.form["due_date"]

        cur.execute("""
            UPDATE announcements
            SET type = %s, subject_id = %s, detail = %s, due_date = %s
            WHERE id = %s
        """, (type_value, subject_id, detail, due_date, id))

        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for("home"))

    cur.execute("SELECT * FROM announcements WHERE id = %s", (id,))
    announcement = cur.fetchone()
    
    cur.execute("SELECT * FROM subjects")
    subjects = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("edit.html", announcement=announcement, subjects=subjects)

@app.route("/search-subjects")
def search_subjects():
    query = request.args.get("q", "").strip()
    
    if not query:
        return {"subjects": []}
    
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM subjects 
        WHERE subject_name ILIKE %s 
        OR teacher_name ILIKE %s
        ORDER BY id ASC
    """, (f"%{query}%", f"%{query}%"))
    
    subjects = cur.fetchall()
    cur.close()
    conn.close()
    
    return {"subjects": subjects}


def format_line_message(rows):
    now_thailand = thai_now()
    
    thai_date = now_thailand.strftime("%d/%m/%Y")
    thai_time = now_thailand.strftime("%H:%M")

    message = "📋 การบ้านและงานค้าง\n"
    message += f"วันที่ {thai_date}\n\n"

    if not rows:
        message += "วันนี้ไม่มีรายการแจ้งจากฝ่ายวิชาการ"
        return message

    for i, row in enumerate(rows, start=1):
        message += f"{i}) {row['type']}\n"
        message += f"วิชา: {row['subject_name']}\n"
        message += f"ครูผู้สอน: {row['teacher_name']}\n"
        message += f"รายละเอียด: {row['detail']}\n"
        message += f"ส่งวันที่: {row['due_date']}\n\n"

    message += "จาก นาย ปัณณ์ สุขส่ง\n"
    message += "(หัวหน้าฝ่ายวิชาการ)\n"
    message += f"ส่งเวลา {thai_time} น.\n"
    message += "   \n"

    return message


@app.route("/shared-calendar")
def shared_calendar():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    now_thailand = thai_now()
    
    year = request.args.get("year", now_thailand.year, type=int)
    month = request.args.get("month", now_thailand.month, type=int)

    # ดึงข้อมูลทั้งเดือน
    cur.execute("""
        SELECT announcements.*, 
               subjects.subject_name, 
               subjects.teacher_name
        FROM announcements
        JOIN subjects ON announcements.subject_id = subjects.id
        WHERE EXTRACT(YEAR FROM announce_date) = %s
        AND EXTRACT(MONTH FROM announce_date) = %s
        ORDER BY announce_date ASC
    """, (year, month))
    
    announcements = cur.fetchall()
    cur.close()
    conn.close()

    # จัดเรียงข้อมูลตามวัน
    announcements_by_date = {}
    for ann in announcements:
        date_str = str(ann['announce_date'])
        if date_str not in announcements_by_date:
            announcements_by_date[date_str] = []
        announcements_by_date[date_str].append(ann)

    # สร้าง Calendar
    cal = monthcalendar(year, month)
    
    # ข้อมูลเดือนก่อน/หลัง
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1

    return render_template("shared_calendar.html", 
                         year=year, 
                         month=month,
                         month_name=THAI_MONTHS_FULL[month],
                         cal=cal,
                         announcements_by_date=announcements_by_date,
                         prev_year=prev_year,
                         prev_month=prev_month,
                         next_year=next_year,
                         next_month=next_month)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)