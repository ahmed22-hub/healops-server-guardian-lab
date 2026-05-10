#!/usr/bin/env bash
set -euo pipefail

echo "Scenario 1: Stop Nginx. HealOps should restart it."
sudo systemctl stop nginx
sleep 25
sudo systemctl status nginx --no-pager || true

echo "Scenario 2: Stop demo Docker container. HealOps should start it."
sudo docker stop demo-web
sleep 25
sudo docker ps --filter name=demo-web

echo "Scenario 3: Generate fake SSH failed logins for security detection."
for i in {1..6}; do
  sudo logger -p authpriv.warning "sshd[12345]: Failed password for invalid user admin from 192.168.56.99 port 55${i} ssh2"
done
sleep 25
sudo journalctl -u healops-agent -n 40 --no-pager

echo "Scenario 4: Generate CPU pressure for 60 seconds."
stress-ng --cpu 2 --timeout 60s --metrics-brief || true
