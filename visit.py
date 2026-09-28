from http.server import BaseHTTPRequestHandler
import json
import os
import time
import urllib.parse
import urllib.request


UPSTASH_URL = os.environ.get("UPSTASH_URL", "").rstrip("/")
UPSTASH_TOKEN = os.environ.get("UPSTASH_TOKEN", "")
LIST_KEY = "visits"
MAX_ITEMS = 500


def redis_post(path: str, body: str) -> bool:
    """إرسال أمر لـ Upstash Redis"""
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return False
    url = f"{UPSTASH_URL}/{path}"
    req = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        headers={
            "Authorization": f"Bearer {UPSTASH_TOKEN}",
            "Content-Type": "text/plain",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status == 200
    except Exception:
        return False


def get_client_ip(headers) -> str:
    """استخراج IP الحقيقي من Vercel"""
    # Vercel بتحط IP في x-forwarded-for
    xff = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()

    # بدائل
    for key in ("x-real-ip", "x-vercel-forwarded-for", "cf-connecting-ip"):
        v = headers.get(key) or headers.get(key.title())
        if v:
            return v.strip()

    return "unknown"


def get_geo(ip: str) -> dict:
    """جلب معلومات جغرافية مجاناً"""
    if not ip or ip in ("unknown", "127.0.0.1", "::1"):
        return {}
    try:
        url = f"http://ip-api.com/json/{urllib.parse.quote(ip)}?fields=status,country,countryCode,regionName,city,isp,org,as,query"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read().decode())
        if data.get("status") == "success":
            return {
                "country": data.get("country"),
                "country_code": data.get("countryCode"),
                "city": data.get("city"),
                "region": data.get("regionName"),
                "isp": data.get("isp"),
                "org": data.get("org"),
                "asn": data.get("as"),
            }
    except Exception:
        pass
    return {}


class handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get("content-length", 0))
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            try:
                payload = json.loads(raw)
            except Exception:
                payload = {}

            ip = get_client_ip(self.headers)
            ua = (self.headers.get("user-agent") or "")[:400]

            geo = get_geo(ip)

            record = {
                "ts": int(time.time()),
                "ip": ip,
                "user_agent": ua,
                "user_id": payload.get("user_id"),
                "username": payload.get("username"),
                "first_name": payload.get("first_name"),
                "last_name": payload.get("last_name"),
                "language": payload.get("language"),
                "is_premium": bool(payload.get("is_premium")),
                "referer": (self.headers.get("referer") or "")[:200],
                "country": geo.get("country"),
                "country_code": geo.get("country_code"),
                "city": geo.get("city"),
                "region": geo.get("region"),
                "isp": geo.get("isp"),
                "org": geo.get("org"),
                "asn": geo.get("asn"),
            }

            # تخزين في Upstash
            ok = redis_post(
                f"lpush/{LIST_KEY}",
                json.dumps(record, ensure_ascii=False),
            )
            # تحديد حجم القائمة
            redis_post(f"ltrim/{LIST_KEY}/0/{MAX_ITEMS - 1}", "")

            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "ok": ok,
                "ip": ip,
                "geo": geo,
            }, ensure_ascii=False).encode("utf-8"))

        except Exception as e:
            self.send_response(500)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())
