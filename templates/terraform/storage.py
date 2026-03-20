from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class StorageTemplate(Template):
    """Generates GCS bucket resources from a parameterized list, each with
    configurable versioning, lifecycle rules, and IAM bindings."""

    def render(self, context: RenderContext) -> GeneratedFile:
        params = context.params
        project = params["project"]
        region = params["region"]
        env = params["environment"]
        buckets = params["buckets"]

        bucket_resources = {}
        iam_resources = {}

        for bucket_cfg in buckets:
            bucket_short_name = bucket_cfg["name"]
            bucket_name = f"{project}-{env}-{bucket_short_name}"
            resource_name = f"{env}_{bucket_short_name.replace('-', '_')}"

            lifecycle_rules = []
            if bucket_cfg.get("lifecycle_age"):
                lifecycle_rules.append(
                    {
                        "action": {"type": "Delete"},
                        "condition": {"age": bucket_cfg["lifecycle_age"]},
                    }
                )
                lifecycle_rules.append(
                    {
                        "action": {"type": "AbortIncompleteMultipartUpload"},
                        "condition": {"age": 7},
                    }
                )

            bucket_resources[resource_name] = {
                "name": bucket_name,
                "project": project,
                "location": region,
                "storage_class": "STANDARD",
                "uniform_bucket_level_access": True,
                "public_access_prevention": "enforced",
                "versioning": {
                    "enabled": bucket_cfg.get("versioning", False),
                },
                "lifecycle_rule": lifecycle_rules,
                "labels": {
                    "environment": env,
                    "managed_by": "geni",
                },
            }

            app_sa_name = f"{params.get('app_name', 'sample-app')}-workload"
            iam_resources[f"{resource_name}_app_access"] = {
                "bucket": f"${{google_storage_bucket.{resource_name}.name}}",
                "role": "roles/storage.objectAdmin",
                "member": f"${{{{\"serviceAccount:${{google_service_account.{app_sa_name}.email}}\"}}}}",
            }

        resources = {
            "resource": {
                "google_storage_bucket": bucket_resources,
                "google_storage_bucket_iam_member": iam_resources,
            }
        }

        return TerraformJSON("storage.tf.json", content=resources)
