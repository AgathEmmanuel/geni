from __future__ import annotations

from geni.template import Template, KubernetesManifest, GeneratedFile, RenderContext


class Namespace(Template):
    """Generates a Kubernetes Namespace manifest.

    Params:
        namespace: name of the namespace
        labels: optional dict of labels
    """

    def render(self, context: RenderContext) -> GeneratedFile:
        manifest = {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": context.params["namespace"],
            },
            "spec": {},
        }

        labels = context.params.get("labels")
        if labels:
            manifest["metadata"]["labels"] = labels

        return KubernetesManifest(f"{self.name}.yml", manifest)
