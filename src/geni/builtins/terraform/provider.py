from __future__ import annotations

from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class Provider(Template):
    """Generates a GCP provider configuration."""

    def render(self, context: RenderContext) -> GeneratedFile:
        return TerraformJSON(f"{self.name}.tf.json", {
            "provider": [{
                "google": [{
                    "project": context.params["project_name"],
                    "region": context.params.get("region", "us-central1")
                }]
            }]
        })
