#!/usr/bin/env bash
# ติดตั้งครั้งเดียวบนเครื่อง Dell (Ubuntu 26.04 "resolute") — ส่วนที่ต้องใช้ sudo
# รัน:  sudo bash ~/classnotify-pro/scripts/dell-setup.sh
# ทำอะไรบ้าง:
#   1. ซ่อม apt sources ให้ตรงกับรุ่น Ubuntu ที่ติดตั้งจริง (เดิมชี้ไป noble ทั้งที่เครื่องเป็น resolute)
#      และลบ repo ที่เสีย (LINE / ngrok)  — สำรองไฟล์เดิมไว้ที่ /etc/apt/backup-<วันที่>/
#   2. ติดตั้ง Docker + Docker Compose จากคลัง Ubuntu และเพิ่ม user เข้า group docker
#   3. ติดตั้ง git, curl, rclone (สำหรับ backup ขึ้น Google Drive)
#   4. ปิด sleep/suspend ให้เครื่องเปิดตลอด
#   5. เปิด ssh และ docker ให้ขึ้นเองหลังรีบูต
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "ต้องรันด้วย sudo: sudo bash $0" >&2
    exit 1
fi

TARGET_USER="${SUDO_USER:-}"
if [[ -z "$TARGET_USER" || "$TARGET_USER" == "root" ]]; then
    echo "หาชื่อ user ไม่ได้ กรุณารันผ่าน sudo จาก user ปกติ" >&2
    exit 1
fi
CODENAME="$(. /etc/os-release && echo "${VERSION_CODENAME:-}")"
if [[ -z "$CODENAME" ]]; then
    echo "อ่าน VERSION_CODENAME จาก /etc/os-release ไม่ได้" >&2
    exit 1
fi
echo "==> user: $TARGET_USER | Ubuntu codename จริง: $CODENAME"

echo "==> [1/5] ซ่อม apt sources"
BACKUP_DIR="/etc/apt/backup-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -a /etc/apt/sources.list "$BACKUP_DIR/" 2>/dev/null || true
cp -a /etc/apt/sources.list.d "$BACKUP_DIR/" 2>/dev/null || true
echo "    สำรองของเดิมไว้ที่ $BACKUP_DIR"

rm -f /etc/apt/sources.list.d/line.list /etc/apt/sources.list.d/ngrok.list

# ถ้า sources.list ยังอ้างถึง codename อื่น ให้เขียนใหม่ให้ตรงรุ่น
if grep -qE "^\s*deb\s" /etc/apt/sources.list 2>/dev/null && ! grep -qE "\b$CODENAME\b" /etc/apt/sources.list; then
    cat > /etc/apt/sources.list <<SRC
deb http://archive.ubuntu.com/ubuntu/ $CODENAME main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu/ $CODENAME-updates main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu/ $CODENAME-security main restricted universe multiverse
SRC
    echo "    เขียน /etc/apt/sources.list ใหม่เป็น $CODENAME"
fi
apt-get update

echo "==> [2/5] ติดตั้ง Docker (จากคลัง Ubuntu)"
apt-get install -y docker.io docker-compose-v2 docker-buildx
usermod -aG docker "$TARGET_USER"
systemctl enable --now docker
docker --version
docker compose version

echo "==> [3/5] ติดตั้ง git curl rclone"
apt-get install -y git curl rclone

echo "==> [4/5] ปิด sleep/suspend"
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
if [[ -f /etc/systemd/logind.conf ]]; then
    sed -i 's/^#\?HandleLidSwitch=.*/HandleLidSwitch=ignore/' /etc/systemd/logind.conf
    sed -i 's/^#\?IdleAction=.*/IdleAction=ignore/' /etc/systemd/logind.conf
fi

echo "==> [5/5] ssh และ docker ขึ้นเองหลังรีบูต"
systemctl enable ssh >/dev/null 2>&1 || true
systemctl enable docker >/dev/null 2>&1 || true

echo
echo "เสร็จแล้ว ✅"
echo "หมายเหตุ: ถ้า user $TARGET_USER มี SSH session ค้างอยู่ ต้องออกแล้วเข้าใหม่เพื่อให้สิทธิ์ docker มีผล"
echo "ตรวจสอบ: docker ps  (ต้องรันได้โดยไม่ต้อง sudo)"
