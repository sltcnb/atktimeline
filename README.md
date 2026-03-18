# ATK Timeline

A self-hosted attack timeline builder for incident response and threat analysis. Built with Flask and PostgreSQL, deployable via Docker Compose or Kubernetes (Traefik).

Map events to **MITRE ATT&CK phases**, track source/destination IPs, artifacts, and IOCs across visual timelines.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Quick Start

### 1. Configure

```bash
cp config.example.json config.json
# Edit config.json with your hostname, passwords, and admin credentials
```

### 2a — Kubernetes

```bash
./auto-deploy.sh
```

Requires: Docker, kubectl, jq, Traefik ingress controller.

### 2b — Docker Compose

```bash
jq -r '"POSTGRES_PASSWORD=\(.postgres_password)\nSECRET_KEY=\(.flask_secret)"' config.json > .env
docker compose up --build
docker compose exec app flask create-user \
  --username admin --email admin@csirt.lab --password changeme
```

Open [http://localhost:8000](http://localhost:8000).

See [deploy.md](deploy.md) for all options including local Python dev.

---

## Features

- **Visual attack timelines** with color-coded MITRE ATT&CK phases
- **Local authentication only** — no public registration, accounts created via CLI
- **PostgreSQL** for production persistence; SQLite for local dev
- **Single config file** (`config.json`) for all deployment settings
- **Kubernetes-ready** with Traefik ingress and automated deployment
- **Clean dark UI** built for SOC/IR analysts
- Track **source IPs, destination IPs, artifacts, and IOCs** per event

---

## MITRE ATT&CK Phases Supported

| Phase | Color |
|---|---|
| Reconnaissance | Indigo |
| Initial Access | Amber |
| Execution | Red |
| Persistence | Rose |
| Privilege Escalation | Dark Red |
| Defense Evasion | Stone |
| Credential Access | Dark Amber |
| Discovery | Sky |
| Lateral Movement | Violet |
| Collection | Teal |
| Exfiltration | Orange |
| Command & Control | Purple |
| Impact | Deep Red |
| Detection | Green |
| Response | Blue |

---

## Project Structure

```
atktimeline/
├── config.example.json     # Deployment config template (copy to config.json)
├── auto-deploy.sh          # Kubernetes deployment script (reads config.json)
├── docker-compose.yml      # Local dev with PostgreSQL
├── Dockerfile
├── requirements.txt
├── app.py                  # Flask application
├── models.py
├── forms.py
├── deploy.md               # Full deployment guide
├── templates/
├── static/
└── k8s/
    ├── postgres-pvc.yaml
    ├── postgres-deployment.yaml
    ├── postgres-service.yaml
    ├── app-deployment.yaml
    └── app-service.yaml
```

---

## User Management

Registration is disabled. All accounts are created via CLI.

```bash
# Docker Compose
docker compose exec app flask create-user \
  --username analyst1 --email analyst1@csirt.lab --password SecurePass123

# Local Python
flask create-user --username analyst1 --email analyst1@csirt.lab --password SecurePass123
```

See [deploy.md](deploy.md) for the Kubernetes equivalent.
