"""นำเข้ารายวิชาจากไฟล์ CSV (คอลัมน์: subject_name,teacher_name)

ตัวอย่าง subjects.csv:
    subject_name,teacher_name
    คณิตศาสตร์,ครูสมชาย
    ภาษาไทย,ครูสมหญิง

ใช้ใน Docker (วางไฟล์ไว้ในโฟลเดอร์โปรเจกต์ก่อน):
    docker compose cp subjects.csv app:/tmp/subjects.csv
    docker compose exec app python scripts/import_subjects.py /tmp/subjects.csv
"""
import csv
import os
import sys

import psycopg2


def main() -> None:
    if len(sys.argv) != 2:
        print("ใช้: python scripts/import_subjects.py <subjects.csv>")
        sys.exit(1)

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ไม่พบ DATABASE_URL ใน environment")
        sys.exit(1)

    with open(sys.argv[1], newline="", encoding="utf-8-sig") as f:
        rows = [
            (r["subject_name"].strip(), r["teacher_name"].strip())
            for r in csv.DictReader(f)
            if r.get("subject_name", "").strip()
        ]

    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO subjects (subject_name, teacher_name) VALUES (%s, %s)",
                rows,
            )
    print(f"นำเข้า {len(rows)} วิชาแล้ว")


if __name__ == "__main__":
    main()
