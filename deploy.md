# Deployment Guide

## Prerequisites

- Docker
- `jq` (`brew install jq` or `apt install jq`)
- For Kubernetes: `kubectl` configured against a running cluster with Traefik

---

## 1. Configure

Copy the example config and fill in your values:

```bash
cp config.example.json config.json
```

Edit `config.json`:

```json
{
  "hostname": "timeline.csirt.lab",
  "namespace": "atktimeline",
  "image": "atktimeline:latest",
  "traefik_entrypoint": "web",
  "admin": {
    "username": "admin",
    "email": "admin@csirt.lab",
    "password": "CHANGE_ME_NOW"
  },
  "postgres_password": "CHANGE_ME_NOW",
  "flask_secret": "CHANGE_ME_NOW"
}
```

`config.json` is gitignored and never committed.

---

## 2a — Kubernetes (production)

```bash
./auto-deploy.sh
```

The script reads `config.json` and:
1. Builds the Docker image
2. Creates the namespace
3. Generates Kubernetes secrets from config values
4. Deploys PostgreSQL with a persistent volume
5. Deploys the Flask app (2 replicas) with Traefik ingress
6. Creates the admin user via a Job

**Access:**

```bash
# Port-forward
kubectl port-forward svc/atktimeline-service 8080:80 -n atktimeline
# → http://localhost:8080

# Traefik ingress (once DNS/hosts resolves your hostname)
# → http://timeline.csirt.lab
```

**Override config path:**

```bash
CONFIG=/path/to/other.json ./auto-deploy.sh
```

---

## 2b — Docker Compose (local)

Generate a `.env` from your `config.json`:

```bash
jq -r '"POSTGRES_PASSWORD=\(.postgres_password)\nSECRET_KEY=\(.flask_secret)"' config.json > .env
```

Then:

```bash
docker compose up --build
```

Open [http://localhost:8000](http://localhost:8000).

Create the first user:

```bash
docker compose exec app flask create-user \
  --username admin --email admin@csirt.lab --password changeme
```

---

## 2c — Local Python (SQLite, no Docker)

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

export FLASK_APP=app.py
flask init-db
flask create-user --username admin --email admin@csirt.lab --password changeme
flask run
# → http://localhost:5000
```

---

## User Management

Registration is disabled. All accounts are created via CLI.

**Kubernetes — add a user after deploy:**

```bash
kubectl run create-user --rm -it --restart=Never \
  --image=atktimeline:latest \
  --namespace=atktimeline \
  --env="FLASK_APP=app.py" \
  --env="DATABASE_URL=postgresql://atktimeline:<POSTGRES_PASSWORD>@postgres-service:5432/atktimeline" \
  --env="SECRET_KEY=<FLASK_SECRET>" \
  -- flask create-user --username analyst1 --email analyst1@csirt.lab --password SecurePass123
```

---

## Useful Kubernetes Commands

```bash
# Logs
kubectl logs -l app=atktimeline -n atktimeline -f

# Restart
kubectl rollout restart deployment/atktimeline -n atktimeline

# Scale
kubectl scale deployment/atktimeline --replicas=3 -n atktimeline

# Tear down
kubectl delete namespace atktimeline
```
