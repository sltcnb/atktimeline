#!/bin/bash
set -e

CONFIG="${CONFIG:-config.json}"

if [ ! -f "$CONFIG" ]; then
  echo "Error: $CONFIG not found."
  echo "Copy config.example.json to config.json, fill in your values, then re-run."
  exit 1
fi

if ! command -v jq &>/dev/null; then
  echo "Error: jq is required. Install it with: brew install jq  or  apt install jq"
  exit 1
fi

cfg() { jq -r "$1" "$CONFIG"; }

HOSTNAME=$(cfg '.hostname')
NAMESPACE=$(cfg '.namespace')
IMAGE=$(cfg '.image')
TLS_SECRET=$(cfg '.tls_secret')
ADMIN_USERNAME=$(cfg '.admin.username')
ADMIN_EMAIL=$(cfg '.admin.email')
ADMIN_PASSWORD=$(cfg '.admin.password')
POSTGRES_PASSWORD=$(cfg '.postgres_password')
FLASK_SECRET=$(cfg '.flask_secret')

DATABASE_URL="postgresql://atktimeline:${POSTGRES_PASSWORD}@postgres-service:5432/atktimeline"

echo "==========================================="
echo " ATK Timeline - Kubernetes Deployment"
echo "==========================================="
echo " Config:     $CONFIG"
echo " Hostname:   $HOSTNAME"
echo " Namespace:  $NAMESPACE"
echo " Image:      $IMAGE"
echo " Admin user: $ADMIN_USERNAME"
echo "==========================================="
echo ""

# ---------------------
# Build Docker image
# ---------------------
echo "[1/6] Building Docker image..."
docker build -t "$IMAGE" .

echo "Importing image into k3s containerd..."
docker save "$IMAGE" | k3s ctr images import -

# ---------------------
# Create namespace
# ---------------------
echo "[2/6] Creating namespace..."
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# ---------------------
# Create secrets
# ---------------------
echo "[3/6] Creating secrets..."

kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: postgres-secret
  namespace: $NAMESPACE
type: Opaque
stringData:
  POSTGRES_DB: "atktimeline"
  POSTGRES_USER: "atktimeline"
  POSTGRES_PASSWORD: "$POSTGRES_PASSWORD"
  DATABASE_URL: "$DATABASE_URL"
EOF

kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: app-secret
  namespace: $NAMESPACE
type: Opaque
stringData:
  SECRET_KEY: "$FLASK_SECRET"
EOF

# ---------------------
# Deploy PostgreSQL
# ---------------------
echo "[4/6] Deploying PostgreSQL..."
kubectl apply -f k8s/postgres-pvc.yaml
kubectl apply -f k8s/postgres-deployment.yaml
kubectl apply -f k8s/postgres-service.yaml

echo "Waiting for PostgreSQL to be ready..."
kubectl wait --for=condition=ready pod -l app=postgres -n "$NAMESPACE" --timeout=120s

# ---------------------
# Deploy app + ingress
# ---------------------
echo "[5/6] Deploying ATK Timeline app..."
kubectl apply -f k8s/app-deployment.yaml
kubectl apply -f k8s/app-service.yaml

# Middleware: redirect HTTP → HTTPS
kubectl apply -f - <<EOF
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: redirect-https
  namespace: $NAMESPACE
spec:
  redirectScheme:
    scheme: https
    permanent: true
EOF

# Ingress: HTTP (redirects to HTTPS)
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: atktimeline-http
  namespace: $NAMESPACE
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: web
    traefik.ingress.kubernetes.io/router.middlewares: ${NAMESPACE}-redirect-https@kubernetescrd
spec:
  ingressClassName: traefik
  rules:
    - host: $HOSTNAME
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: atktimeline-service
                port:
                  number: 80
EOF

# Ingress: HTTPS
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: atktimeline-https
  namespace: $NAMESPACE
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: websecure
    traefik.ingress.kubernetes.io/router.tls: "true"
spec:
  ingressClassName: traefik
  tls:
    - hosts:
        - $HOSTNAME
      secretName: $TLS_SECRET
  rules:
    - host: $HOSTNAME
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: atktimeline-service
                port:
                  number: 80
EOF

echo "Waiting for app to be ready..."
kubectl wait --for=condition=ready pod -l app=atktimeline -n "$NAMESPACE" --timeout=120s

# ---------------------
# Create admin user
# ---------------------
echo "[6/6] Creating admin user..."
kubectl delete job create-admin-user -n "$NAMESPACE" --ignore-not-found

kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: create-admin-user
  namespace: $NAMESPACE
spec:
  ttlSecondsAfterFinished: 300
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: create-user
          image: $IMAGE
          imagePullPolicy: IfNotPresent
          command:
            - flask
            - create-user
            - --username
            - "$ADMIN_USERNAME"
            - --email
            - "$ADMIN_EMAIL"
            - --password
            - "$ADMIN_PASSWORD"
          env:
            - name: FLASK_APP
              value: "app.py"
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: postgres-secret
                  key: DATABASE_URL
            - name: SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: app-secret
                  key: SECRET_KEY
  backoffLimit: 3
EOF

kubectl wait --for=condition=complete job/create-admin-user -n "$NAMESPACE" --timeout=60s

# ---------------------
# Summary
# ---------------------
echo ""
echo "==========================================="
echo " Deployment complete!"
echo "==========================================="
echo ""
echo " Admin credentials:"
echo "   Username: $ADMIN_USERNAME"
echo "   Password: $ADMIN_PASSWORD"
echo ""
echo " Port-forward:"
echo "   kubectl port-forward svc/atktimeline-service 8080:80 -n $NAMESPACE"
echo "   → http://localhost:8080"
echo ""
echo " Traefik ingress (HTTP redirects to HTTPS):"
echo "   → https://$HOSTNAME"
echo "==========================================="
