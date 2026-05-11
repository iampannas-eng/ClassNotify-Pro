from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import requests
import os
from dotenv import load_dotenv
from calendar import monthcalendar, month_name
from datetime import datetime, timedelta, timezone


load_dotenv()

# ✅ ดึงค่าจาก Environment Variables (Render จะตั้งให้)
DATABASE_URL = os.getenv("DATABASE_URL")
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")

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
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    today = datetime.now().strftime("%Y-%m-%d")

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
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and user["password"] == password:
            session["user_id"] = user["id"]
            return redirect(url_for("home"))
        else:
            return "Login Failed"

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))



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
        
        # ✅ Thailand Timezone
        thailand_tz = timezone(timedelta(hours=7))
        now_thailand = datetime.now(thailand_tz)
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

    cur.execute("SELECT * FROM subjects")
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
    today = datetime.now().strftime("%Y-%m-%d")

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


def format_line_message(rows):
    # ✅ เพิ่ม timezone Thailand
    thailand_tz = timezone(timedelta(hours=7))
    now_thailand = datetime.now(thailand_tz)
    
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
    message += "นี่คือการทดสอบระบบครั้งที่ 1 (เวอร์ชั่น 6.7)"

    return message


@app.route("/shared-calendar")
def shared_calendar():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # ✅ Thailand Timezone
    thailand_tz = timezone(timedelta(hours=7))
    now_thailand = datetime.now(thailand_tz)
    
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
                         month_name=month_name[month],
                         cal=cal,
                         announcements_by_date=announcements_by_date,
                         prev_year=prev_year,
                         prev_month=prev_month,
                         next_year=next_year,
                         next_month=next_month)

if __name__ == "__main__":
    app.run(debug=True)