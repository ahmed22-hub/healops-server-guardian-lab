#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

log() { echo "[healops-node] $*"; }

log "Installing demo application containers"
rm -rf /opt/healops/node
mkdir -p /opt/healops/node
cp -r /vagrant/compose/node/* /opt/healops/node/
cd /opt/healops/node
docker compose up -d

log "Configuring Nginx reverse proxy"
cat >/etc/nginx/sites-available/healops <<'EOF'
server {
    listen 80 default_server;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8088;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
EOF
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/healops /etc/nginx/sites-enabled/healops
nginx -t
systemctl enable --now nginx
systemctl restart nginx

log "Installing HealOps agent"
python3 -m venv /opt/healops/venv
/opt/healops/venv/bin/pip install --upgrade pip
/opt/healops/venv/bin/pip install -r /vagrant/scripts/requirements.txt
cp /vagrant/healops/agent.py /opt/healops/bin/healops-agent.py
chmod +x /opt/healops/bin/healops-agent.py

cat >/etc/systemd/system/healops-agent.service <<'EOF'
[Unit]
Description=HealOps Server Guardian Agent
After=network-online.target docker.service nginx.service
Wants=network-online.target docker.service

[Service]
Type=simple
ExecStart=/opt/healops/venv/bin/python /opt/healops/bin/healops-agent.py
Restart=always
RestartSec=3
Environment=NODE_NAME=healops-node1
Environment=CONTROL_API=http://192.168.56.10:5000/incident
Environment=CHECK_INTERVAL=15
Environment=AUTO_FIX=true
Environment=BLOCK_IPS=false
Environment=TELEGRAM_BOT_TOKEN=
Environment=TELEGRAM_CHAT_ID=

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now healops-agent

log "Firewall rules"
ufw allow OpenSSH || true
ufw allow 80/tcp || true
ufw allow from 192.168.56.10 to any port 9100 proto tcp || true
ufw allow from 192.168.56.10 to any port 8080 proto tcp || true
ufw --force enable || true

log "Node VM ready"
log "Web demo: http://localhost:8088"
log "Agent logs: sudo journalctl -u healops-agent -f"
