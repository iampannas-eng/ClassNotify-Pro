"""ส่งออก /api/today เป็นไฟล์ JSON ไปยัง URL คงที่ (GitHub Gist) สำหรับจอทีวีในห้องเรียน

ทำไม: กล่องทีวีอาจไม่ได้อยู่วงแลนเดียวกับเครื่อง Dell และ URL ของ Quick Tunnel เปลี่ยนทุกครั้งที่รีสตาร์ท
จึงให้ฝั่ง Dell เป็นผู้ "ส่งออก" ข้อมูลไปที่ Gist ซึ่งมี URL คงที่ แล้วกล่องอ่านจากที่เดียวตลอด

การทำงาน (รันเป็น service `exporter` ใน docker-compose):
  - ทุก EXPORT_INTERVAL วินาที (ค่าเริ่มต้น 60) ดึง http://app:8000/api/today
    และทันทีที่แอปเขียนไฟล์ธง export/.changed (หลังเพิ่ม/แก้/ลบประกาศ)
  - เขียนลง export/today.json เสมอ (มีประโยชน์เวลาอยู่วงแลนเดียวกัน หรือเอาไปใช้ทางอื่น)
  - ถ้ามี GIST_TOKEN ใน .env: อัปเดต Gist (สร้างใหม่ครั้งแรกแล้วจำ id ไว้ใน export/gist_id.txt)
    และอัปโหลดเฉพาะเมื่อเนื้อหาเปลี่ยน เพื่อไม่ให้ชน rate limit ของ GitHub

สร้าง token ที่ GitHub > Settings > Developer settings > Personal access tokens (classic) เลือก scope "gist"
"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import requests

API_URL = os.environ.get("EXPORT_SOURCE_URL", "http://app:8000/api/today")
INTERVAL = int(os.environ.get("EXPORT_INTERVAL", "60"))
EXPORT_DIR = Path(os.environ.get("EXPORT_DIR", "export"))
GIST_TOKEN = os.environ.get("GIST_TOKEN", "").strip()
GIST_ID = os.environ.get("GIST_ID", "").strip()
GIST_FILE = "today.json"
GITHUB_API = "https://api.github.com"


def log(msg: str) -> None:
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


def fetch_today() -> dict:
    r = requests.get(API_URL, timeout=15)
    r.raise_for_status()
    return r.json()


def gist_headers() -> dict:
    return {
        "Authorization": f"Bearer {GIST_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def load_gist_id() -> str:
    if GIST_ID:
        return GIST_ID
    f = EXPORT_DIR / "gist_id.txt"
    return f.read_text().strip() if f.is_file() else ""


def save_gist_id(gist_id: str) -> None:
    (EXPORT_DIR / "gist_id.txt").write_text(gist_id)


def raw_url(gist: dict) -> str:
    """URL คงที่ของไฟล์ล่าสุดใน Gist (ไม่ผูกกับ commit)"""
    owner = gist.get("owner", {}).get("login", "")
    return f"https://gist.githubusercontent.com/{owner}/{gist['id']}/raw/{GIST_FILE}"


def publish_to_gist(payload_text: str) -> None:
    gist_id = load_gist_id()
    body = {"files": {GIST_FILE: {"content": payload_text}}}
    if gist_id:
        r = requests.patch(f"{GITHUB_API}/gists/{gist_id}", headers=gist_headers(), json=body, timeout=20)
        if r.status_code == 404:
            log(f"Gist {gist_id} ไม่พบ (ถูกลบ?) จะสร้างใหม่")
            gist_id = ""
        else:
            r.raise_for_status()
            log(f"อัปเดต Gist แล้ว: {raw_url(r.json())}")
            return
    body.update({"description": "ClassNotify: งานที่ต้องส่งวันนี้ (สร้างอัตโนมัติ)", "public": False})
    r = requests.post(f"{GITHUB_API}/gists", headers=gist_headers(), json=body, timeout=20)
    r.raise_for_status()
    gist = r.json()
    save_gist_id(gist["id"])
    log(f"สร้าง Gist ใหม่ id={gist['id']}")
    log(f"URL สำหรับกล่องทีวี: {raw_url(gist)}")
    (EXPORT_DIR / "gist_url.txt").write_text(raw_url(gist))


def run_once(last_hash: str) -> str:
    data = fetch_today()
    text = json.dumps(data, ensure_ascii=False, indent=1)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    (EXPORT_DIR / GIST_FILE).write_text(text, encoding="utf-8")

    # เนื้อหาที่ "มีผล" ไม่รวม generated_at เพื่อไม่อัปโหลดซ้ำทุกรอบทั้งที่ข้อมูลเท่าเดิม
    stable = dict(data)
    stable.pop("generated_at", None)
    digest = hashlib.sha256(json.dumps(stable, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    if not GIST_TOKEN:
        if last_hash == "":
            log("ไม่มี GIST_TOKEN: เขียนเฉพาะไฟล์ export/today.json (ตั้งค่าใน .env เพื่อส่งขึ้น Gist)")
        return digest
    if digest != last_hash:
        publish_to_gist(text)
    return digest


CHANGED_FLAG = EXPORT_DIR / ".changed"   # แอปเขียนไฟล์นี้เมื่อมีการเพิ่ม/แก้/ลบประกาศ
POLL_SECONDS = 3


def main() -> None:
    once = "--once" in sys.argv
    last_hash = ""
    last_run = 0.0
    while True:
        changed = CHANGED_FLAG.exists()
        due = (time.time() - last_run) >= INTERVAL
        if changed or due or last_run == 0.0:
            if changed:
                try:
                    CHANGED_FLAG.unlink()
                except OSError:
                    pass
                log("ข้อมูลเปลี่ยน: ส่งออกทันที")
            try:
                last_hash = run_once(last_hash)
            except Exception as e:  # ห้ามให้ service ตายเพราะเน็ตหลุดชั่วคราว
                log(f"ผิดพลาด: {e}")
            last_run = time.time()
            if once:
                break
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
