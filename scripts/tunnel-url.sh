#!/usr/bin/env bash
# แสดง URL สาธารณะปัจจุบันของ Cloudflare Quick Tunnel
cd "$(dirname "${BASH_SOURCE[0]}")/.."
URL="$(docker compose logs --no-log-prefix cloudflared 2>/dev/null | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1)"
if [[ -z "$URL" ]]; then
    echo "ยังไม่พบ URL (cloudflared อาจยังไม่ขึ้น) ลอง: docker compose logs cloudflared" >&2
    exit 1
fi
echo "$URL"
