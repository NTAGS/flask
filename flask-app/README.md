# Flask Enterprise Commerce — Kubernetes + Observability POC

A deliberately realistic commerce workload for practicing enterprise Kubernetes, Helm, CI/CD and end-to-end observability patterns.

## Business flow

1. Login as the POC user (credentials come from a Kubernetes Secret).
2. Browse **5 categories × 2 products = 10 products**.
3. Select product + quantity and create an order.
4. An asynchronous Redis-backed worker progresses the order through `PLACED -> CONFIRMED -> PROCESSING -> SHIPPED -> DELIVERED`.
5. List/check order status.
6. Cancel or reorder.
7. Repeated order submissions can use `Idempotency-Key` to avoid duplicate orders.
8. Requests emit structured logs, Prometheus metrics and OpenTelemetry traces.

## Architecture

```text
kubectl -> HAProxy:8443 -> Kubernetes API servers

Users -> NGINX Ingress -> Flask Service -> Flask Pods
                                      |-> Redis
                                      |-> PostgreSQL StatefulSet -> PVC
                                      `-> OTel Collector -> Jaeger / Splunk

Flask /metrics -> Prometheus -> Grafana
```

HAProxy and NGINX are intentionally separate. HAProxy fronts the Kubernetes control-plane API for `kubectl`; NGINX Ingress handles application/user HTTP(S) traffic.

## Kubernetes coverage

- Flask Deployment (3 replicas) + ClusterIP Service
- **NGINX Ingress** for application/user traffic
- PostgreSQL StatefulSet + **PVC**
- Redis Deployment
- Helm **Job hook** for database migration + seed data
- Alembic migration (`migrations/versions/0001_initial.py`)
- ConfigMap + Secret / externally supplied Secret support
- ServiceAccount + permissionless Role/RoleBinding (least-privilege workload identity)
- HPA + PodDisruptionBudget
- readiness/liveness probes
- CPU/memory requests and limits
- topology spread across nodes
- NetworkPolicy with explicit ingress/egress for application, worker, PostgreSQL and Redis
- Prometheus scrape annotations

## Observability

```text
Flask -> OTLP HTTP -> OTel Collector -> Jaeger (traces)
                                  `-> Splunk HEC (logs)

Flask /metrics -> Prometheus -> Grafana
```

For AWS, **do not configure `localhost` from application pods**. The collector must be reachable through private DNS/IP, VPN/tunnel, or a load balancer. Your existing local Mac observability stack is suitable for development, but AWS pods need a reachable endpoint rather than Mac `localhost`.

## Local validation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q

cp .env.example .env
# Set a real JWT_SECRET and, if used, a real SPLUNK_HEC_TOKEN.

docker compose config
docker compose up --build -d

curl http://localhost:8000/health/live
curl http://localhost:8000/api/v1/products
```

Jaeger: `http://localhost:16686`
Prometheus: `http://localhost:9090`

## Helm

The default chart expects an existing Kubernetes Secret named `flask-commerce-secret`. This is intentional: production deployments should not put real credentials in Git or ordinary Helm values.

Example Secret:

```bash
kubectl -n commerce create secret generic flask-commerce-secret \
  --from-literal=POSTGRES_PASSWORD='CHANGE_ME' \
  --from-literal=JWT_SECRET='CHANGE_ME_LONG_RANDOM' \
  --from-literal=ADMIN_USERNAME='admin' \
  --from-literal=ADMIN_PASSWORD='password'
```

Then:

```bash
helm lint helm/flask-commerce
helm template commerce helm/flask-commerce \
  --set image.repository=YOUR_DOCKERHUB_USER/flask-commerce \
  --set image.tag=1.0.0

helm upgrade --install commerce helm/flask-commerce \
  --namespace commerce --create-namespace \
  --set image.repository=YOUR_DOCKERHUB_USER/flask-commerce \
  --set image.tag=1.0.0
```

For a learning environment where Helm should create the Secret, use `values.local.example.yaml` as a starting point and supply real local values outside Git.

Install an NGINX Ingress Controller in the cluster before enabling the Ingress resource. The chart assumes the ingress class is `nginx`.

## Jenkins

`Jenkinsfile` is stored in Git. It runs:

1. unit tests
2. Docker image build for `linux/amd64`
3. Docker Hub push
4. Helm lint/template validation
5. Helm deployment using a dedicated kubeconfig credential
6. rollout verification

The Jenkins agent definition is in `ci/Dockerfile` and includes Docker CLI, Helm and kubectl. The Docker socket is mounted only for this build-agent pattern; in a hardened enterprise setup, use a dedicated image-builder such as Kaniko/BuildKit instead of a Docker socket.

The Kubernetes credential should be **namespace-scoped / least privilege**, not a cluster-admin kubeconfig.

## Validation script

```bash
./scripts/validate.sh
```

It performs Python compilation, YAML checks for non-template YAML, Helm lint/template when Helm is installed, and Docker build/Compose validation when Docker is available.

## Production boundary

This is an interview/learning POC designed to exercise real enterprise Kubernetes patterns. The Flask application and manifests intentionally demonstrate production practices, but a real bank deployment would normally use:

- managed or independently operated HA PostgreSQL rather than an application-owned single-replica database
- managed/HA Redis
- enterprise identity (OIDC/LDAP/SSO) instead of the demo username/password login
- external secret management such as Vault or a cloud secret manager
- centralized OTel/Prometheus/Grafana/Splunk platforms
- hardened CI agents/builders without Docker socket access
- GitOps or controlled CD promotion for production
- image signing/scanning and admission policies
- multiple availability zones and backup/restore procedures

## Apple Silicon note

The development Mac is Apple Silicon while the AWS Kubernetes nodes are amd64. The Jenkins pipeline therefore builds the container with `--platform linux/amd64`. If you build manually on the Mac for AWS, use the same platform explicitly or use `docker buildx`.
