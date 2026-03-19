from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class IamTemplate(Template):
    """Generates IAM resources including service accounts, project-level IAM
    bindings, and Workload Identity configuration for GKE workloads."""

    def render(self, context: RenderContext) -> GeneratedFile:
        params = context.params
        project = params["project"]
        env = params["environment"]
        app_name = params["app_name"]
        cluster_name = params["cluster_name"]
        app_namespace = params["app_namespace"]

        app_sa_name = f"{app_name}-workload"
        compute_sa_name = f"{env}-compute"
        sql_proxy_sa_name = f"{env}-sql-proxy"

        resources = {
            "resource": {
                "google_service_account": {
                    app_sa_name: {
                        "account_id": app_sa_name,
                        "project": project,
                        "display_name": f"Workload Identity SA for {app_name}",
                        "description": f"Service account used by {app_name} pods via Workload Identity in {env}",
                    },
                    compute_sa_name: {
                        "account_id": compute_sa_name,
                        "project": project,
                        "display_name": f"Compute instance SA for {env}",
                        "description": f"Service account attached to compute instances in {env}",
                    },
                    sql_proxy_sa_name: {
                        "account_id": sql_proxy_sa_name,
                        "project": project,
                        "display_name": f"Cloud SQL Proxy SA for {env}",
                        "description": f"Service account for Cloud SQL Proxy connections in {env}",
                    },
                },
                "google_project_iam_member": {
                    f"{app_sa_name}-storage-viewer": {
                        "project": project,
                        "role": "roles/storage.objectViewer",
                        "member": f"${{{{\"serviceAccount:${{google_service_account.{app_sa_name}.email}}\"}}}}",
                    },
                    f"{app_sa_name}-log-writer": {
                        "project": project,
                        "role": "roles/logging.logWriter",
                        "member": f"${{{{\"serviceAccount:${{google_service_account.{app_sa_name}.email}}\"}}}}",
                    },
                    f"{compute_sa_name}-log-writer": {
                        "project": project,
                        "role": "roles/logging.logWriter",
                        "member": f"${{{{\"serviceAccount:${{google_service_account.{compute_sa_name}.email}}\"}}}}",
                    },
                    f"{compute_sa_name}-monitoring-writer": {
                        "project": project,
                        "role": "roles/monitoring.metricWriter",
                        "member": f"${{{{\"serviceAccount:${{google_service_account.{compute_sa_name}.email}}\"}}}}",
                    },
                    f"{sql_proxy_sa_name}-sql-client": {
                        "project": project,
                        "role": "roles/cloudsql.client",
                        "member": f"${{{{\"serviceAccount:${{google_service_account.{sql_proxy_sa_name}.email}}\"}}}}",
                    },
                },
                "google_service_account_iam_member": {
                    f"{app_sa_name}-workload-identity": {
                        "service_account_id": f"${{google_service_account.{app_sa_name}.name}}",
                        "role": "roles/iam.workloadIdentityUser",
                        "member": f"serviceAccount:{project}.svc.id.goog[{app_namespace}/{app_name}]",
                    },
                },
            }
        }

        return TerraformJSON(name="iam", content=resources)
