from geni.template import Template, KubernetesManifest, RenderContext


class MonitoringTemplate(Template):
    """Render a monitoring-stack Helm chart via render_helm, then customize.

    Demonstrates the render_helm feature: a Python template that renders a
    local Helm chart, then post-processes the manifests — injecting labels,
    filtering resources, and adding environment-specific annotations.
    """

    def render(self, context: RenderContext):
        p = context.params

        manifests = context.render_helm(
            chart=p["chart_path"],
            release_name=f"{p['environment']}-monitoring",
            values={
                "namespace": p["namespace"],
                "prometheus": {
                    "image": p.get("prometheus_image", "prom/prometheus:v2.50.0"),
                    "replicas": p.get("prometheus_replicas", 1),
                    "retention": p.get("retention", "15d"),
                    "storageSize": p.get("storage_size", "10Gi"),
                    "resources": p.get("prometheus_resources", {
                        "requests": {"cpu": "250m", "memory": "512Mi"},
                        "limits": {"cpu": "500m", "memory": "1Gi"},
                    }),
                },
                "grafana": {
                    "image": p.get("grafana_image", "grafana/grafana:10.3.0"),
                    "replicas": p.get("grafana_replicas", 1),
                    "resources": p.get("grafana_resources", {
                        "requests": {"cpu": "100m", "memory": "256Mi"},
                        "limits": {"cpu": "250m", "memory": "512Mi"},
                    }),
                },
            },
            namespace=p["namespace"],
        )

        results = []
        for m in manifests:
            kind = m.get("kind", "unknown")

            # Inject environment and project labels into every manifest
            metadata = m.setdefault("metadata", {})
            labels = metadata.setdefault("labels", {})
            labels["environment"] = p["environment"]
            labels["project"] = p["project"]

            # Add annotation for alert routing on Deployments
            if kind == "Deployment":
                annotations = metadata.setdefault("annotations", {})
                annotations["geni.io/environment"] = p["environment"]
                if p.get("alert_channel"):
                    annotations["monitoring.geni.io/alert-channel"] = p["alert_channel"]

            filename = f"monitoring-{kind.lower()}-{metadata.get('name', 'unknown')}.yml"
            results.append(KubernetesManifest(filename, m))

        return results
