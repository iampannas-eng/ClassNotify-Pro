FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Bangkok

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# 2 worker พอสำหรับผู้ใช้ไม่กี่คน, timeout 60 วินาทีเผื่อ LINE API ช้า
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:8000", "--timeout", "60", "--access-logfile", "-", "app:app"]
