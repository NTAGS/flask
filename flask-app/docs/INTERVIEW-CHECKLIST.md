# Interview checklist

- HAProxy: Kubernetes API/control-plane endpoint; not application ingress.
- NGINX Ingress: user/application HTTP(S) routing to Services.
- NetworkPolicy egress: controls pod outbound traffic.
- Deployment: stateless Flask replicas.
- StatefulSet + PVC: PostgreSQL persistence.
- Redis: queue/cache; worker advances order status.
- Job: database initialization/seed hook.
- HPA: horizontal pod scaling from CPU.
- PDB/topology spread: availability during disruption and node maintenance.
- ServiceAccount/RBAC: workload identity and least privilege.
- ConfigMap/Secret: non-sensitive vs sensitive configuration.
- Probes/resources: scheduling and health.
- OTel Collector: telemetry routing boundary.
- Jaeger: distributed traces.
- Prometheus/Grafana: metrics.
- Splunk HEC: centralized logs.
- Jenkins: test -> build -> push -> Helm validate -> deploy -> rollout verify.
