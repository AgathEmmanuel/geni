from __future__ import annotations

from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext
from geni.filters import sanitize_terraform_name


class Services(Template):
    """Generates Google Cloud project service enablement resources.

    Params:
        project_name: GCP project ID
        services: list of service APIs to enable
    """

    def render(self, context: RenderContext) -> GeneratedFile:
        services_block = {}
        for svc in context.params.get("services", []):
            key = sanitize_terraform_name(svc) + "_key"
            services_block[key] = {
                "project": context.params["project_name"],
                "service": svc,
            }

        return TerraformJSON(f"{self.name}.tf.json", {
            "resource": [{
                "google_project_service": [services_block]
            }]
        })
