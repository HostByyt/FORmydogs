from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.parse
import urllib.request


UPSTASH_URL = os.environ.get("UPSTASH_URL", "").rstrip("/")
UPSTASH_TOKEN = os.environ.get("UPSTASH_TOKEN", "")
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "change-me")
LIST_KEY = "visits"


def redis_get(path: str):
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return None
    url = f"{UPSTASH_URL}/{path}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        secret = (params.get("secret") or [""])[0]
        limit = int((params.get("limit") or ["20"])[0])
        limit = max(1, min(limit, 100))

        if secret != ADMIN_SECRET:
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": "forbidden"}).encode())
            return

        result = redis_get(f"lrange/{LIST_KEY}/0/{limit - 1}")
        items = []
        if isinstance(result, dict) and "result" in result:
            for raw in result["result"]:
                try:
                    items.append(json.loads(raw))
                except Exception:
                    continue

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({
            "ok": True,
            "count": len(items),
            "items": items,
        }, ensure_ascii=False).encode("utf-8"))
