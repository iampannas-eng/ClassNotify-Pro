#!/usr/bin/env bash
# กู้คืนฐานข้อมูลจากไฟล์ backup
# ใช้: scripts/restore.sh backups/classnotify_20260101_020000.sql.gz
# คำเตือน: ข้อมูลปัจจุบันในฐานข้อมูลจะถูกแทนที่ทั้งหมด
set -euo pipefail

if [[ $# -ne 1 || ! -f "$1" ]]; then
    echo "ใช้: $0 <ไฟล์ .sql.gz>" >&2
    exit 1
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
set -a
# shellcheck disable=SC1091
source .env
set +a

FILE="$(realpath "$1")"
read -r -p "จะเขียนทับฐานข้อมูล '$POSTGRES_DB' ด้วย $FILE ใช่ไหม? (พิมพ์ yes): " ANSWER
[[ "$ANSWER" == "yes" ]] || { echo "ยกเลิก"; exit 0; }

gunzip -c "$FILE" | docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1
echo "กู้คืนเสร็จแล้ว"
