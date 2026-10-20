# Observability

The application exposes `/metrics` for Prometheus scraping and emits OpenTelemetry traces/logs through OTLP HTTP.

- Traces: OTel Collector -> Jaeger
- Logs: OTel Collector -> Splunk HEC (set `SPLUNK_HEC_ENDPOINT` and `SPLUNK_HEC_TOKEN`)
- Metrics: Prometheus -> `/metrics` -> Grafana (point Grafana at Prometheus)

For AWS, do not use `localhost` from pods. Publish the central collector on a reachable private DNS/IP, VPN/tunnel, or load balancer and set `OTEL_EXPORTER_OTLP_ENDPOINT` accordingly.
