#!/usr/bin/env bash
# สำรองฐานข้อมูล ClassNotify Pro
#  - pg_dump จาก container db -> backups/classnotify_YYYYmmdd_HHMMSS.sql.gz
#  - เก็บในเครื่อง 14 วัน
#  - ถ้าตั้ง rclone remote ชื่อ gdrive ไว้ จะอัปโหลดขึ้น Google Drive โฟลเดอร์ classnotify-backups ด้วย
#
# ตั้ง cron (crontab -e) ให้รันทุกวัน 02:00:
#   0 2 * * * /home/pannasuksong/classnotify-pro/scripts/backup.sh >> /home/pannasuksong/classnotify-pro/backups/backup.log 2>&1
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# โหลดค่าจาก .env
set -a
# shellcheck disable=SC1091
source .env
set +a

BACKUP_DIR="$PROJECT_DIR/backups"
mkdir -p "$BACKUP_DIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
FILE="$BACKUP_DIR/classnotify_${STAMP}.sql.gz"

echo "[$(date '+%F %T')] เริ่ม backup -> $FILE"
docker compose exec -T db pg_dump -U "$POSTGRES_USER" --clean --if-exists "$POSTGRES_DB" | gzip > "$FILE"

SIZE="$(du -h "$FILE" | cut -f1)"
echo "[$(date '+%F %T')] สำเร็จ ขนาด $SIZE"

# ลบไฟล์เก่ากว่า 14 วันในเครื่อง
find "$BACKUP_DIR" -name 'classnotify_*.sql.gz' -mtime +14 -delete

# อัปโหลดขึ้น Google Drive ถ้ามี rclone และ remote ชื่อ gdrive
if command -v rclone >/dev/null 2>&1 && rclone listremotes | grep -q '^gdrive:'; then
    rclone copy "$FILE" gdrive:classnotify-backups
    # บน Drive เก็บ 60 วัน
    rclone delete --min-age 60d gdrive:classnotify-backups || true
    echo "[$(date '+%F %T')] อัปโหลดขึ้น Google Drive แล้ว"
else
    echo "[$(date '+%F %T')] ไม่พบ rclone remote 'gdrive' ข้ามการอัปโหลด"
fi
