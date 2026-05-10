# HealOps Server Guardian Lab

Un laboratoire DevSecOps avec deux machines virtuelles. Il surveille un serveur Linux complet, detecte des pannes et des signaux de securite simples, puis applique des actions de self-healing.

## Ce que le lab cree

- VM `control` - 192.168.56.10
  - Grafana sur http://localhost:3000
  - Prometheus sur http://localhost:9090
  - HealOps Incident API sur http://localhost:5000
- VM `node1` - 192.168.56.11
  - Reverse proxy Nginx
  - Application Docker demo `demo-web`
  - Node Exporter et cAdvisor
  - Agent HealOps comme service systemd

## Prerequis sur la machine host

Installer VirtualBox et Vagrant.

## Lancement

```bash
unzip healops_server_guardian_lab.zip
cd healops-server-guardian-lab
vagrant up
```

## Acces

- Grafana: http://localhost:3000 - utilisateur `admin`, mot de passe `admin`
- Prometheus: http://localhost:9090
- Incident API: http://localhost:5000/health
- Application demo: http://localhost:8088

## Scenarios de demonstration

```bash
vagrant ssh node1
cd /vagrant
./scripts/demo_scenarios.sh
```

Scenarios manuels:

```bash
sudo systemctl stop nginx
sudo docker stop demo-web
sudo journalctl -u healops-agent -f
```

## Blocage securite optionnel

L'agent detecte les echecs SSH repetes. Par defaut, il ne bloque pas les IPs pour eviter les lockouts dans le lab. Pour activer le blocage, modifier le service systemd et mettre:

```bash
Environment=BLOCK_IPS=true
```

Puis executer:

```bash
sudo systemctl daemon-reload
sudo systemctl restart healops-agent
```
