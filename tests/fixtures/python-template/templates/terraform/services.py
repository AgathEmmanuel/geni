from geni.template import Template, TerraformJSON, RenderContext, GeneratedFile
from geni.filters import sanitize_terraform_name


class Services(Template):
    """Generate service enablement resources from a list."""

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
