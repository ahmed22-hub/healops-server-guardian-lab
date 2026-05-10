#!/usr/bin/env python3
"""HealOps Server Guardian Agent."""

import datetime as dt
import json
import os
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path

import psutil
import requests

try:
    from healops.anomaly import detect_spike
    from healops.prometheus_client import get_cpu_usage
except ImportError:
    from anomaly import detect_spike
    from prometheus_client import get_cpu_usage

from email_alerts import send_email_alert


NODE_NAME = os.getenv("NODE_NAME", socket.gethostname())
CONTROL_API = os.getenv("CONTROL_API", "http://192.168.56.10:5000/incident")
INTERVAL = int(os.getenv("CHECK_INTERVAL", "15"))
AUTO_FIX = os.getenv("AUTO_FIX", "true").lower() == "true"
BLOCK_IPS = os.getenv("BLOCK_IPS", "false").lower() == "true"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

LOG_DIR = Path("/var/log/healops-agent")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "incidents.jsonl"

COOLDOWN_SECONDS = 60
last_sent = {}

SUSPICIOUS_PORTS = {4444, 5555, 1337, 31337}


def now_iso():
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def run(cmd, timeout=10):
    return subprocess.run(cmd, shell=True, text=True, capture_output=True, timeout=timeout)


def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=5)
        print("telegram_alert_sent=true", flush=True)
    except Exception as exc:
        print(f"telegram_error={exc}", flush=True)


def send_high_severity_notifications(data):
    severity = data["severity"]
    typ = data["type"]
    message = data["message"]
    action = data["action"]

    if severity.lower() not in {"high", "critical"}:
        return

    telegram_text = (
        f"[{severity.upper()}] {typ} on {NODE_NAME}: {message}. "
        f"Action: {action}"
    )
    send_telegram(telegram_text)

    email_subject = f"[{severity.upper()}] HealOps Incident: {typ}"
    email_body = f"""HealOps Server Guardian Alert

Node: {NODE_NAME}
Type: {typ}
Severity: {severity}
Message: {message}
Action: {action}
Time: {data["time"]}

Evidence:
{json.dumps(data.get("evidence", {}), indent=2)}
"""
    send_email_alert(email_subject, email_body)


def incident(typ, severity, message, action="none", evidence=None):
    key = (typ, severity, message)
    current = time.time()

    if current - last_sent.get(key, 0) < COOLDOWN_SECONDS:
        return

    last_sent[key] = current

    data = {
        "time": now_iso(),
        "node": NODE_NAME,
        "type": typ,
        "severity": severity,
        "message": message,
        "action": action,
        "evidence": evidence or {},
    }

    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(data, sort_keys=True) + "\n")

    print(json.dumps(data, sort_keys=True), flush=True)

    try:
        requests.post(CONTROL_API, json=data, timeout=4)
    except Exception as exc:
        print(f"control_api_error={exc}", flush=True)

    send_high_severity_notifications(data)


def check_nginx():
    result = run("systemctl is-active --quiet nginx")

    if result.returncode != 0:
        action = "no action"

        if AUTO_FIX:
            restart = run("systemctl restart nginx")
            if restart.returncode == 0:
                action = "systemctl restart nginx"
            else:
                action = f"restart failed: {restart.stderr.strip()}"

        incident("nginx_down", "high", "Nginx service is not active", action)


def check_demo_container():
    result = run("docker inspect -f '{{.State.Running}}' demo-web")
    running = result.stdout.strip().lower() == "true"

    if not running:
        action = "no action"

        if AUTO_FIX:
            start = run("docker start demo-web")
            if start.returncode == 0:
                action = "docker start demo-web"
            else:
                action = f"start failed: {start.stderr.strip()}"

        incident("container_down", "high", "Docker container demo-web is not running", action)


def check_resources():
    cpu = psutil.cpu_percent(interval=0.2)
    mem = psutil.virtual_memory().percent
    disk = shutil.disk_usage("/")
    disk_pct = round((disk.used / disk.total) * 100, 1)

    if cpu >= 90:
        incident("high_cpu", "medium", f"CPU usage is {cpu}%", "alert only", {"cpu_percent": cpu})

    if mem >= 90:
        incident("high_memory", "medium", f"Memory usage is {mem}%", "alert only", {"memory_percent": mem})

    if disk_pct >= 85:
        incident("high_disk", "medium", f"Disk usage is {disk_pct}%", "alert only", {"disk_percent": disk_pct})


def check_ssh_failures():
    auth_log = Path("/var/log/auth.log")

    if not auth_log.exists():
        return

    try:
        lines = auth_log.read_text(encoding="utf-8", errors="ignore").splitlines()[-300:]
    except Exception:
        return

    ips = {}

    for line in lines:
        if "Failed password" not in line:
            continue

        match = re.search(r"from (\d+\.\d+\.\d+\.\d+)", line)

        if match:
            ip = match.group(1)
            ips[ip] = ips.get(ip, 0) + 1

    for ip, count in ips.items():
        if count >= 5:
            action = "alert only"

            if BLOCK_IPS:
                result = run(f"ufw deny from {ip}")

                if result.returncode == 0:
                    action = f"ufw deny from {ip}"
                else:
                    action = f"block failed: {result.stderr.strip()}"

            incident(
                "ssh_bruteforce",
                "high",
                f"{count} failed SSH logins from {ip}",
                action,
                {"source_ip": ip, "count": count},
            )


def check_suspicious_ports():
    result = run("ss -ltnp", timeout=5)

    if result.returncode != 0:
        return

    for line in result.stdout.splitlines():
        match = re.search(r":(\d+)\s", line)

        if not match:
            continue

        port = int(match.group(1))

        if port in SUSPICIOUS_PORTS:
            incident(
                "suspicious_port",
                "high",
                f"Suspicious listening port detected: {port}",
                "alert only",
                {"line": line},
            )


def check_anomalies():
    try:
        cpu_metrics = get_cpu_usage()
    except Exception as exc:
        incident(
            "anomaly_engine_error",
            "medium",
            f"Failed to query Prometheus: {exc}",
            "no action",
        )
        return

    baseline = [20, 21, 22, 20, 19, 21, 20, 22, 19, 20]

    for metric in cpu_metrics:
        instance = metric.get("metric", {}).get("instance", "unknown")
        current_cpu = float(metric["value"][1])

        result = detect_spike(current_cpu, baseline)

        if result.is_anomaly:
            incident(
                "cpu_anomaly",
                result.level,
                f"CPU anomaly detected on {instance}: {current_cpu:.2f}%",
                "alert only",
                {
                    "instance": instance,
                    "current_cpu": round(current_cpu, 2),
                    "anomaly_score": result.score,
                    "anomaly_level": result.level,
                    "baseline_mean": result.baseline_mean,
                    "baseline_std": result.baseline_std,
                    "reason": result.reason,
                },
            )


def main():
    print(
        f"HealOps agent started on {NODE_NAME}; "
        f"control_api={CONTROL_API}; "
        f"auto_fix={AUTO_FIX}; "
        f"block_ips={BLOCK_IPS}",
        flush=True,
    )

    while True:
        try:
            check_nginx()
            check_demo_container()
            check_resources()
            check_ssh_failures()
            check_suspicious_ports()
            check_anomalies()
        except Exception as exc:
            incident("agent_error", "medium", f"Agent error: {exc}", "no action")

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()