from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class OutputsTemplate(Template):
    """Generates Terraform outputs for all major resources: GKE cluster,
    Cloud SQL, networking, compute, storage, and IAM."""

    def render(self, context: RenderContext) -> GeneratedFile:
        params = context.params
        env = params["environment"]
        cluster_name = params["cluster_name"]
        db_instance_name = params["db_instance_name"]
        network_name = params["network_name"]

        subnet_name = f"{network_name}-subnet"
        instance_name = f"{env}-bastion"
        app_sa_name = "sample-app-workload"
        compute_sa_name = f"{env}-compute"
        sql_proxy_sa_name = f"{env}-sql-proxy"

        outputs = {
            "output": {
                "cluster_name": {
                    "description": "GKE cluster name",
                    "value": f"${{google_container_cluster.{cluster_name}.name}}",
                },
                "cluster_endpoint": {
                    "description": "GKE cluster endpoint",
                    "value": f"${{google_container_cluster.{cluster_name}.endpoint}}",
                    "sensitive": True,
                },
                "cluster_ca_certificate": {
                    "description": "GKE cluster CA certificate (base64-encoded)",
                    "value": f"${{google_container_cluster.{cluster_name}.master_auth[0].cluster_ca_certificate}}",
                    "sensitive": True,
                },
                "database_instance_name": {
                    "description": "Cloud SQL instance name",
                    "value": f"${{google_sql_database_instance.{db_instance_name}.name}}",
                },
                "database_connection_name": {
                    "description": "Cloud SQL connection name for cloud-sql-proxy",
                    "value": f"${{google_sql_database_instance.{db_instance_name}.connection_name}}",
                },
                "database_private_ip": {
                    "description": "Cloud SQL private IP address",
                    "value": f"${{google_sql_database_instance.{db_instance_name}.private_ip_address}}",
                    "sensitive": True,
                },
                "database_password": {
                    "description": "Cloud SQL user password",
                    "value": f"${{random_password.{db_instance_name}_password.result}}",
                    "sensitive": True,
                },
                "vpc_self_link": {
                    "description": "VPC network self link",
                    "value": f"${{google_compute_network.{network_name}.self_link}}",
                },
                "subnet_self_link": {
                    "description": "Subnet self link",
                    "value": f"${{google_compute_subnetwork.{subnet_name}.self_link}}",
                },
                "bastion_external_ip": {
                    "description": "Bastion host external IP address",
                    "value": f"${{google_compute_instance.{instance_name}.network_interface[0].access_config[0].nat_ip}}",
                },
                "app_service_account_email": {
                    "description": "Application workload service account email",
                    "value": f"${{google_service_account.{app_sa_name}.email}}",
                },
                "compute_service_account_email": {
                    "description": "Compute instance service account email",
                    "value": f"${{google_service_account.{compute_sa_name}.email}}",
                },
                "sql_proxy_service_account_email": {
                    "description": "Cloud SQL Proxy service account email",
                    "value": f"${{google_service_account.{sql_proxy_sa_name}.email}}",
                },
            }
        }

        return TerraformJSON("outputs.tf.json", content=outputs)
