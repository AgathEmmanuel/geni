from __future__ import annotations

from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext
from geni.filters import sanitize_terraform_name


class Bucket(Template):
    """Generates one or more GCS bucket resources.

    Params:
        buckets: list of dicts with 'name', 'location' (optional)
        OR
        bucket_name: str (single bucket)
        location: str (default "US")
        project: str
    """

    def render(self, context: RenderContext) -> GeneratedFile:
        buckets = context.params.get("buckets", [])

        if not buckets:
            # Single bucket mode
            buckets = [{
                "name": context.params["bucket_name"],
                "location": context.params.get("location", "US"),
            }]

        resources = {}
        for b in buckets:
            key = sanitize_terraform_name(b["name"])
            resources[key] = {
                "name": b["name"],
                "location": b.get("location", "US"),
                "project": context.params.get("project", context.data.get("project")),
                "uniform_bucket_level_access": True,
                "force_destroy": False,
                "public_access_prevention": "enforced",
                "versioning": [{"enabled": True}],
            }

        return TerraformJSON(f"{self.name}.tf.json", {
            "resource": [{
                "google_storage_bucket": [resources]
            }]
        })
