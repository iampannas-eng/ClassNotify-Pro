#!/usr/bin/env bash
# ใส่ GIST_TOKEN ลง .env แบบไม่แสดงบนหน้าจอ แล้วสร้าง container exporter ใหม่ให้อ่านค่า
# ใช้: bash scripts/set-gist-token.sh   (รันบน Dell)
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "วาง GitHub token (scope: gist) แล้วกด Enter — จะไม่แสดงตัวอักษรขณะพิมพ์"
read -r -s -p "GIST_TOKEN: " token
echo
if [[ -z "$token" ]]; then
    echo "ไม่ได้ใส่ค่า ยกเลิก" >&2
    exit 1
fi

# แทนที่บรรทัดเดิมถ้ามี ไม่มีก็เพิ่มใหม่
if grep -qE '^GIST_TOKEN=' .env; then
    sed -i "s|^GIST_TOKEN=.*|GIST_TOKEN=${token}|" .env
else
    printf '\nGIST_TOKEN=%s\n' "$token" >> .env
fi
chmod 600 .env
unset token
echo "บันทึกลง .env แล้ว กำลังสร้าง container exporter ใหม่..."

docker compose up -d --force-recreate exporter >/dev/null
echo "รอ exporter ส่งข้อมูลรอบแรก..."
for _ in $(seq 1 30); do
    if [[ -s export/gist_url.txt ]]; then
        echo
        echo "สำเร็จ URL สำหรับกล่องทีวี:"
        cat export/gist_url.txt
        echo
        exit 0
    fi
    sleep 2
done
echo "ยังไม่เห็น export/gist_url.txt ดู log ด้วย: docker compose logs --tail 20 exporter" >&2
docker compose logs --no-log-prefix --tail 10 exporter >&2
exit 1
