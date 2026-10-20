-- ClassNotify Pro : โครงสร้างฐานข้อมูล
-- ไฟล์นี้จะถูกรันอัตโนมัติครั้งแรกที่ container postgres สร้าง volume ใหม่
-- (ผ่าน /docker-entrypoint-initdb.d) หรือรันเองด้วย: psql -U classnotify -d classnotify -f schema.sql

CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    username    TEXT NOT NULL UNIQUE,
    password    TEXT NOT NULL            -- เก็บเป็น hash (werkzeug) ไม่ใช่ plain text
);

CREATE TABLE IF NOT EXISTS subjects (
    id              SERIAL PRIMARY KEY,
    subject_name    TEXT NOT NULL,
    teacher_name    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS announcements (
    id              SERIAL PRIMARY KEY,
    type            TEXT NOT NULL,                       -- การบ้าน / งานค้าง / รายงาน / ...
    subject_id      INTEGER NOT NULL REFERENCES subjects(id),
    detail          TEXT NOT NULL,
    announce_date   DATE NOT NULL,
    due_date        DATE NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_announcements_announce_date ON announcements (announce_date);
CREATE INDEX IF NOT EXISTS idx_announcements_subject_id    ON announcements (subject_id);
