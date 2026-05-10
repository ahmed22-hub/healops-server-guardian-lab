# HealOps Server Guardian Lab

A two-VM DevSecOps lab that monitors a complete Linux server, detects failures and simple security signals, and applies safe self-healing actions.

## What it creates

- `control` VM - 192.168.56.10
  - Grafana on http://localhost:3000
  - Prometheus on http://localhost:9090
  - HealOps Incident API on http://localhost:5000
- `node1` VM - 192.168.56.11
  - Nginx reverse proxy
  - Demo Docker app `demo-web`
  - Node Exporter and cAdvisor
  - HealOps agent as a systemd service

## Host requirements

Install VirtualBox and Vagrant on your host machine.

## Run

```bash
unzip healops_server_guardian_lab.zip
cd healops-server-guardian-lab
vagrant up
```

## Access

- Grafana: http://localhost:3000 - user `admin`, password `admin`
- Prometheus: http://localhost:9090
- Incident API: http://localhost:5000/health
- Demo app: http://localhost:8088

## Demo scenarios

```bash
vagrant ssh node1
cd /vagrant
./scripts/demo_scenarios.sh
```

Manual scenarios:

```bash
sudo systemctl stop nginx
sudo docker stop demo-web
sudo journalctl -u healops-agent -f
```

## Optional security blocking

The agent detects repeated SSH failures. By default it does not block IPs to avoid lab lockouts. To enable blocking, edit the systemd service and set:

```bash
Environment=BLOCK_IPS=true
```

Then run:

```bash
sudo systemctl daemon-reload
sudo systemctl restart healops-agent
```
