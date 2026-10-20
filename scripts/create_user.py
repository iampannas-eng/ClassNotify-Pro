"""สร้างหรือเปลี่ยนรหัสผ่านผู้ใช้หลังบ้าน (เก็บเป็น hash)

ใช้ใน Docker:
    # แบบถามรหัสผ่าน (ต้องมี TTY)
    docker compose exec -it app python scripts/create_user.py <username>
    # แบบระบุรหัสผ่านในคำสั่ง (ไม่ต้องพิมพ์ตอนถาม)
    docker compose exec -T app python scripts/create_user.py <username> --password <รหัส>
หรือรันตรงๆ โดยมี DATABASE_URL ใน environment
"""
import argparse
import getpass
import os
import sys

import psycopg2
from werkzeug.security import generate_password_hash


def main() -> None:
    parser = argparse.ArgumentParser(description="สร้าง/เปลี่ยนรหัสผ่านผู้ใช้หลังบ้าน")
    parser.add_argument("username", help="ชื่อผู้ใช้")
    parser.add_argument("--password", "-p", help="รหัสผ่าน (ถ้าไม่ระบุจะถามแบบซ่อนตัวอักษร)")
    args = parser.parse_args()

    username = args.username.strip()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ไม่พบ DATABASE_URL ใน environment")
        sys.exit(1)

    if args.password is not None:
        password = args.password
    else:
        password = getpass.getpass("รหัสผ่านใหม่: ")
        confirm = getpass.getpass("ยืนยันรหัสผ่าน: ")
        if password != confirm:
            print("รหัสผ่านไม่ตรงกัน")
            sys.exit(1)

    if not password:
        print("รหัสผ่านว่างเปล่า")
        sys.exit(1)

    hashed = generate_password_hash(password)

    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (username, password)
                VALUES (%s, %s)
                ON CONFLICT (username) DO UPDATE SET password = EXCLUDED.password
                """,
                (username, hashed),
            )
    print(f"บันทึกผู้ใช้ '{username}' แล้ว")


if __name__ == "__main__":
    main()
