#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

pass() { echo "PASS: $1"; }
warn() { echo "WARN: $1"; }

python3 -m compileall -q app tests migrations
pass "Python compilation"

python3 - <<'PY'
import yaml
from pathlib import Path
for p in [Path('docker-compose.yml'), Path('observability/otel-local.yaml'), Path('observability/prometheus.yml'), Path('helm/flask-commerce/Chart.yaml'), Path('helm/flask-commerce/values.yaml'), Path('values.local.example.yaml')]:
    yaml.safe_load(p.read_text())
print('PASS: YAML syntax for non-Helm-template files')
PY

if command -v pytest >/dev/null 2>&1; then
  pytest -q
  pass "pytest"
else
  warn "pytest not installed; run: python3 -m pip install -r requirements-dev.txt"
fi

if command -v helm >/dev/null 2>&1; then
  helm lint helm/flask-commerce
  helm template commerce helm/flask-commerce \
    --set image.repository=example/flask-commerce \
    --set image.tag=test \
    --set secret.create=false \
    --set secret.existingSecret=flask-commerce-secret \
    >/tmp/flask-commerce-rendered.yaml
  grep -q 'kind: Deployment' /tmp/flask-commerce-rendered.yaml
  grep -q 'kind: StatefulSet' /tmp/flask-commerce-rendered.yaml
  grep -q 'kind: Job' /tmp/flask-commerce-rendered.yaml
  grep -q 'kind: Ingress' /tmp/flask-commerce-rendered.yaml
  grep -q 'kind: NetworkPolicy' /tmp/flask-commerce-rendered.yaml
  pass "Helm lint/template and required resources"
else
  warn "Helm not installed; install Helm and rerun for native chart validation."
fi

if command -v docker >/dev/null 2>&1; then
  docker build -t flask-commerce:validation .
  docker compose config >/tmp/flask-compose-rendered.yaml
  pass "Docker build and Compose config"
else
  warn "Docker not installed; run docker build and docker compose config locally."
fi

echo "Validation complete."
