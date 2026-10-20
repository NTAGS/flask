# Validation Report — Flask Enterprise Commerce V2

Date: 2026-10-04

## Static validation completed

- Python source compilation: PASS (`app`, `tests`, `migrations`)
- YAML parsing: PASS for non-Helm YAML (`docker-compose.yml`, observability configs, chart metadata, values files)
- Helm template files were not passed to a generic YAML parser because raw Helm Go-template expressions are not valid standalone YAML.
- Source scan: no private-key/token patterns detected
- No `.DS_Store`, `.pytest_cache`, or `__pycache__` artifacts included in the final package
- Stale `db.*` SQLAlchemy references removed; the application consistently uses `DB`
- Application metrics use Flask route templates (`request.url_rule.rule`) rather than raw order URLs, avoiding high-cardinality Prometheus labels
- Database initialization uses an Alembic migration job plus seed data, not `create_all()` in the runtime application
- Helm defaults use an externally supplied Secret; real credentials are not stored in chart defaults
- NGINX Ingress TLS is controlled by `ingress.tls.enabled`
- Jenkins builds explicitly for `linux/amd64`, matching the AWS Kubernetes nodes
- Jenkins agent includes Docker CLI, Helm and kubectl
- NetworkPolicies cover Flask, worker, PostgreSQL and Redis traffic

## Native checks that must be run on the target Mac/CI environment

The build environment used to assemble this archive does not have network access for Python package installation and does not provide Docker/Helm binaries. Therefore the following were intentionally **not claimed as executed here**:

- `python -m pytest -q` with freshly installed dependencies
- `helm lint`
- `helm template`
- `docker build`
- `docker compose config`
- `docker compose up`

Run:

```bash
./scripts/validate.sh
```

The script performs those checks when the corresponding tools/dependencies are available.
