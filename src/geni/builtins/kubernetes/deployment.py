from __future__ import annotations

from geni.template import Template, KubernetesManifest, GeneratedFile, RenderContext


class Deployment(Template):
    """Generates a Kubernetes Deployment manifest.

    Params:
        name: deployment name
        namespace: target namespace
        image: container image
        replicas: number of replicas (default 1)
        port: container port (default 8080)
        app: app label (defaults to name)
        container_name: container name (defaults to name)
    """

    def render(self, context: RenderContext) -> GeneratedFile:
        p = context.params
        name = p["name"]
        app = p.get("app", name)

        manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": name,
                "namespace": p.get("namespace", "default"),
            },
            "spec": {
                "replicas": p.get("replicas", 1),
                "selector": {
                    "matchLabels": {"app": app},
                },
                "template": {
                    "metadata": {
                        "labels": {"app": app},
                    },
                    "spec": {
                        "containers": [{
                            "name": p.get("container_name", name),
                            "image": p["image"],
                            "ports": [{"containerPort": p.get("port", 8080)}],
                        }],
                    },
                },
            },
        }

        return KubernetesManifest(f"{self.name}.yml", manifest)
