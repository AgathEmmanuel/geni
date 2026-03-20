from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class KubernetesTemplate(Template):
    """Generates a GKE Autopilot cluster with private networking, Workload
    Identity, and master authorized networks."""

    def render(self, context: RenderContext) -> GeneratedFile:
        params = context.params
        project = params["project"]
        region = params["region"]
        env = params["environment"]
        cluster_name = params["cluster_name"]
        network_name = params["network_name"]

        subnet_name = f"{network_name}-subnet"

        resources = {
            "resource": {
                "google_container_cluster": {
                    cluster_name: {
                        "name": cluster_name,
                        "project": project,
                        "location": region,
                        "enable_autopilot": True,
                        "network": f"${{google_compute_network.{network_name}.id}}",
                        "subnetwork": f"${{google_compute_subnetwork.{subnet_name}.id}}",
                        "ip_allocation_policy": {
                            "cluster_secondary_range_name": f"{env}-pods",
                            "services_secondary_range_name": f"{env}-services",
                        },
                        "private_cluster_config": {
                            "enable_private_nodes": True,
                            "enable_private_endpoint": False,
                            "master_ipv4_cidr_block": "172.16.0.0/28",
                        },
                        "master_authorized_networks_config": {
                            "cidr_blocks": [
                                {
                                    "cidr_block": "0.0.0.0/0",
                                    "display_name": "All networks (restrict in production)",
                                }
                            ],
                        },
                        "release_channel": {
                            "channel": "REGULAR",
                        },
                        "workload_identity_config": {
                            "workload_pool": f"{project}.svc.id.goog",
                        },
                        "cluster_autoscaling": {
                            "auto_provisioning_defaults": {
                                "service_account": f"${{google_service_account.{env}-compute.email}}",
                                "oauth_scopes": [
                                    "https://www.googleapis.com/auth/cloud-platform",
                                ],
                            }
                        },
                        "deletion_protection": False,
                        "resource_labels": {
                            "environment": env,
                            "managed_by": "geni",
                        },
                    }
                }
            }
        }

        return TerraformJSON("kubernetes.tf.json", content=resources)
