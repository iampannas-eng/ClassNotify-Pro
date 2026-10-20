# คู่มือติดตั้ง ClassNotify Pro บนเครื่อง Dell (Linux) + Cloudflare Tunnel

> ภาพรวม: ผู้ใช้ → Cloudflare (HTTPS) → Tunnel → Dell → Docker (app + PostgreSQL)
> ทุกคำสั่งด้านล่างรันบน Dell ผ่าน SSH ยกเว้นที่ระบุว่าทำบน Cloudflare dashboard

## 0. เตรียมเครื่อง Dell (ทำครั้งเดียว ผ่าน Remote Desktop)

```bash
# เปิด SSH เพื่อให้เข้ามาทำงานจากเครื่อง Windows ได้
sudo apt update
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
sudo systemctl status ssh --no-pager      # ต้องเห็น active (running)

# ถ้ามี firewall (ufw) เปิดอยู่ ให้อนุญาต port 22
sudo ufw status
sudo ufw allow 22/tcp

# จดค่าเหล่านี้ไว้
whoami            # ชื่อ user
ip -4 addr        # IP ปัจจุบัน (คาดว่า 192.168.1.69)
cat /etc/os-release | head -3
```

จากเครื่อง Windows ทดสอบ: `ssh <user>@192.168.1.69`

แนะนำ: ตั้ง DHCP reservation ที่ router ให้ Dell ได้ IP 192.168.1.69 ตลอด
และปิด sleep/suspend: `sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target`

## 1. ติดตั้ง Docker, rclone และตั้งค่าเครื่อง (ครั้งเดียว)

ใช้สคริปต์ที่เตรียมไว้ (ซ่อม apt sources ให้ตรงรุ่น Ubuntu 26.04, ลบ repo LINE/ngrok ที่เสีย, ติดตั้ง Docker/rclone/git จากคลัง Ubuntu, เพิ่ม user เข้า group docker, ปิด sleep):

```bash
sudo bash ~/classnotify-pro/scripts/dell-setup.sh
# ออกจาก SSH แล้วเข้าใหม่ 1 ครั้ง เพื่อให้สิทธิ์ docker มีผล
docker ps
```

## 2. วางโค้ด

```bash
git clone https://github.com/iampannas-eng/ClassNotify-Pro.git ~/classnotify-pro
cd ~/classnotify-pro
cp .env.example .env
nano .env     # กรอก POSTGRES_PASSWORD, DATABASE_URL, SECRET_KEY, LINE_*, (TUNNEL_TOKEN ใส่ทีหลังในข้อ 4)
chmod 600 .env
chmod +x scripts/*.sh
```

สุ่ม SECRET_KEY: `python3 -c "import secrets; print(secrets.token_hex(32))"`

## 3. รันครั้งแรก (ยังไม่ต้องมี Cloudflare)

```bash
docker compose up -d --build db app
docker compose ps                   # db และ app ต้อง healthy
docker compose logs -f app          # Ctrl+C เพื่อออก
curl http://localhost:8000/health   # ต้องได้ {"status":"ok"}
```

สร้างผู้ใช้หลังบ้านและนำเข้าวิชา:

```bash
# แบบถามรหัสผ่าน (ถ้าพิมพ์ไม่ได้ ใช้แบบที่สองแทน)
docker compose exec -it app python scripts/create_user.py admin
# แบบระบุรหัสผ่านในคำสั่ง
docker compose exec -T app python scripts/create_user.py admin --password <รหัส>

# เตรียม subjects.csv (หัวคอลัมน์ subject_name,teacher_name) แล้ว
docker compose cp subjects.csv app:/tmp/subjects.csv
docker compose exec app python scripts/import_subjects.py /tmp/subjects.csv
```

ทดสอบจากเครื่องในบ้าน: http://192.168.1.69:8000

## 4. Cloudflare Tunnel (Quick Tunnel ฟรี)

docker-compose ตั้งค่าเป็นโหมด Quick Tunnel อยู่แล้ว ไม่ต้องสมัคร Cloudflare หรือมีโดเมน

```bash
docker compose up -d                 # เริ่ม cloudflared ด้วย
./scripts/tunnel-url.sh              # แสดง URL สาธารณะปัจจุบัน เช่น https://xxxx.trycloudflare.com
```

ข้อจำกัด: URL เป็นชื่อสุ่ม และ **เปลี่ยนใหม่ทุกครั้งที่ container cloudflared รีสตาร์ท** (เช่น Dell รีบูต)
ถ้าต้องการ URL ถาวร ต้องมีโดเมนในบัญชี Cloudflare แล้วสลับเป็น Named Tunnel ตามคอมเมนต์ใน docker-compose.yml:
Zero Trust → Networks → Tunnels → Create → Docker → คัดลอก token ใส่ `TUNNEL_TOKEN` ใน .env
→ Public Hostname: Type HTTP, URL `app:8000`

เมื่อใช้ผ่าน Cloudflare ได้แล้ว แนะนำปิดการเข้าตรงจาก LAN โดยแก้ `docker-compose.yml`
`ports: - "127.0.0.1:8000:8000"` แล้ว `docker compose up -d`

## 5. Backup

สคริปต์ `scripts/backup.sh` รันทุกวัน 02:00 ผ่าน cron เก็บไฟล์ไว้ใน `backups/` 14 วัน (ตั้งค่าไว้แล้ว)

### (ไม่บังคับ) สำเนาขึ้น Google Drive

ถ้าตั้ง rclone remote ชื่อ `gdrive` สคริปต์จะอัปโหลดให้อัตโนมัติ ถ้าไม่ตั้งจะข้ามไป

```bash
sudo apt install -y rclone
rclone config
#  n) New remote  → name: gdrive  → storage: drive
#  client_id/secret เว้นว่าง → scope: 1 (full access)
#  "Use web browser to automatically authenticate?" ตอบ n (เพราะ Dell ไม่มีจอผ่าน SSH)
#  ทำตามคำสั่ง rclone authorize ที่ขึ้นมา บนเครื่อง Windows แล้ววาง token กลับ
rclone mkdir gdrive:classnotify-backups
rclone lsd gdrive:

# ทดสอบ backup
./scripts/backup.sh
ls -lh backups/
rclone ls gdrive:classnotify-backups

# ตั้ง cron ทุกวัน 02:00
crontab -e
# เพิ่มบรรทัด:
# 0 2 * * * /home/pannasuksong/classnotify-pro/scripts/backup.sh >> /home/pannasuksong/classnotify-pro/backups/backup.log 2>&1
```

กู้คืน: `./scripts/restore.sh backups/classnotify_YYYYmmdd_HHMMSS.sql.gz`

## 6. สลับจาก Render (ทำเมื่อทุกอย่างบน Dell นิ่งแล้ว)

1. LINE Developers Console → Messaging API → เปลี่ยน **Webhook URL** เป็น `https://classnotify.<โดเมน>/webhook`
2. ทดสอบกดส่ง LINE จากหน้า Dashboard บน Dell (ตอนนี้ยังไม่ทำ รอคำสั่งก่อน)
3. แจ้ง URL ใหม่ให้ผู้ใช้ปฏิทิน `/shared-calendar`
4. เปิด Render ทิ้งไว้ 1-2 สัปดาห์เป็นทางหนี แล้วค่อย suspend

## 7. ดูแลประจำวัน

```bash
cd /home/pannasuksong/classnotify-pro
docker compose ps                        # สถานะ
docker compose logs --tail=100 app       # log แอป
git pull && docker compose up -d --build # อัปเดตโค้ด
docker compose restart cloudflared       # ถ้า tunnel หลุด
```

ตารางเวลา: ทุกอย่างอยู่ใน Asia/Bangkok แล้ว (ทั้ง container และโค้ด)
