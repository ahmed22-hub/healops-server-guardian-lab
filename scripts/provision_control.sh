#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

log() { echo "[healops-control] $*"; }

log "Installing incident API"
install -m 0755 -d /opt/healops/bin /var/log/healops
cp /vagrant/healops/incident_api.py /opt/healops/bin/incident_api.py
chmod +x /opt/healops/bin/incident_api.py

cat >/etc/systemd/system/healops-incident-api.service <<'EOF'
[Unit]
Description=HealOps Incident API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/healops/bin/incident_api.py
Restart=always
RestartSec=3
Environment=HEALOPS_API_HOST=0.0.0.0
Environment=HEALOPS_API_PORT=5000
Environment=HEALOPS_LOG_FILE=/var/log/healops/incidents.jsonl

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now healops-incident-api

log "Installing monitoring stack"
rm -rf /opt/healops/control
mkdir -p /opt/healops/control
cp -r /vagrant/compose/control/* /opt/healops/control/
mkdir -p /opt/healops/control/grafana-data
chown -R 472:472 /opt/healops/control/grafana-data || true
cd /opt/healops/control
docker compose up -d

log "Firewall rules"
ufw allow OpenSSH || true
ufw allow 3000/tcp || true
ufw allow 9090/tcp || true
ufw allow 5000/tcp || true
ufw --force enable || true

log "Control VM ready"
log "Grafana: http://localhost:3000 (admin/admin)"
log "Prometheus: http://localhost:9090"
log "Incident API: http://localhost:5000/health"
