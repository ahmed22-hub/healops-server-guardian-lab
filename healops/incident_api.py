#!/usr/bin/env python3
"""Small incident API for HealOps.
Receives JSON incidents from agents and exposes Prometheus metrics.
No external Python dependency is required.
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from collections import Counter
import json, os, re, time

HOST = os.getenv("HEALOPS_API_HOST", "0.0.0.0")
PORT = int(os.getenv("HEALOPS_API_PORT", "5000"))
LOG_FILE = Path(os.getenv("HEALOPS_LOG_FILE", "/var/log/healops/incidents.jsonl"))
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

LABEL_RE = re.compile(r"[^a-zA-Z0-9_:.-]")

def clean_label(value):
    value = str(value or "unknown")[:80]
    return LABEL_RE.sub("_", value)

def read_incidents():
    if not LOG_FILE.exists():
        return []
    rows = []
    for line in LOG_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows

def metrics_text():
    incidents = read_incidents()
    c = Counter()
    for item in incidents:
        node = clean_label(item.get("node", "unknown"))
        typ = clean_label(item.get("type", "unknown"))
        sev = clean_label(item.get("severity", "unknown"))
        c[(node, typ, sev)] += 1
    lines = [
        "# HELP healops_incidents_total Total HealOps incidents received by the control API",
        "# TYPE healops_incidents_total counter",
    ]
    if not c:
        lines.append('healops_incidents_total{node="none",type="none",severity="none"} 0')
    for (node, typ, sev), value in sorted(c.items()):
        lines.append(f'healops_incidents_total{{node="{node}",type="{typ}",severity="{sev}"}} {value}')
    lines.append("# HELP healops_api_up HealOps incident API health")
    lines.append("# TYPE healops_api_up gauge")
    lines.append("healops_api_up 1")
    return "\n".join(lines) + "\n"

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, content_type="application/json"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/health"):
            self._send(200, json.dumps({"status": "ok", "time": int(time.time())}))
        elif self.path.startswith("/metrics"):
            self._send(200, metrics_text(), "text/plain; version=0.0.4")
        elif self.path.startswith("/incidents"):
            self._send(200, json.dumps(read_incidents()[-50:], indent=2))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if not self.path.startswith("/incident"):
            self._send(404, json.dumps({"error": "not found"}))
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            self._send(400, json.dumps({"error": "invalid json", "detail": str(exc)}))
            return
        data.setdefault("received_at", int(time.time()))
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(data, sort_keys=True) + "\n")
        print("incident", json.dumps(data, sort_keys=True), flush=True)
        self._send(201, json.dumps({"status": "stored"}))

    def log_message(self, fmt, *args):
        print("api", self.address_string(), fmt % args, flush=True)

if __name__ == "__main__":
    print(f"HealOps incident API listening on {HOST}:{PORT}", flush=True)
    HTTPServer((HOST, PORT), Handler).serve_forever()
