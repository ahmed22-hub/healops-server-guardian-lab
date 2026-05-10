#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

log() { echo "[healops-common] $*"; }

log "Updating packages"
apt-get update -y
apt-get install -y \
  ca-certificates curl gnupg lsb-release apt-transport-https \
  software-properties-common git unzip jq vim net-tools iproute2 \
  python3 python3-pip python3-venv python3-dev build-essential \
  nginx ufw fail2ban stress-ng

if ! command -v docker >/dev/null 2>&1; then
  log "Installing Docker Engine"
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
  log "Docker already installed"
fi

systemctl enable --now docker
usermod -aG docker vagrant || true
mkdir -p /opt/healops/bin /var/log/healops /var/lib/healops
chmod 755 /opt/healops
log "Common provisioning completed"
