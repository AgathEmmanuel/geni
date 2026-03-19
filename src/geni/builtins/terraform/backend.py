from __future__ import annotations

from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class Backend(Template):
    """Generates a Terraform GCS backend configuration."""

    def render(self, context: RenderContext) -> GeneratedFile:
        return TerraformJSON(f"{self.name}.tf.json", {
            "terraform": [{
                "backend": [{
                    "gcs": {
                        "bucket": [context.params["bucket_name"]],
                        "prefix": [context.params.get("tfstate_prefix", self.name)]
                    }
                }]
            }]
        })
