from __future__ import annotations

from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class GKEAutopilot(Template):
    """Generates a GKE Autopilot cluster with VPC and subnet.

    Params:
        project_name: GCP project ID
        region: GCP region (default us-central1)
    """

    def render(self, context: RenderContext) -> GeneratedFile:
        project = context.params["project_name"]
        region = context.params.get("region", "us-central1")

        return TerraformJSON(f"{self.name}.tf.json", {
            "resource": [
                {
                    "google_compute_network": [{
                        "default": {
                            "name": f"{project}-network",
                            "auto_create_subnetworks": False,
                            "enable_ula_internal_ipv6": True,
                        }
                    }]
                },
                {
                    "google_compute_subnetwork": [{
                        "default": {
                            "name": f"{project}-subnetwork",
                            "ip_cidr_range": "10.0.0.0/16",
                            "region": region,
                            "stack_type": "IPV4_IPV6",
                            "ipv6_access_type": "INTERNAL",
                            "network": "${google_compute_network.default.id}",
                            "secondary_ip_range": [
                                {
                                    "range_name": "services-range",
                                    "ip_cidr_range": "192.168.0.0/24",
                                },
                                {
                                    "range_name": "pod-ranges",
                                    "ip_cidr_range": "192.168.1.0/24",
                                },
                            ],
                        }
                    }]
                },
                {
                    "google_container_cluster": [{
                        "default": {
                            "name": f"{project}-autopilot-cluster",
                            "location": region,
                            "enable_autopilot": True,
                            "enable_l4_ilb_subsetting": True,
                            "network": "${google_compute_network.default.id}",
                            "subnetwork": "${google_compute_subnetwork.default.id}",
                            "ip_allocation_policy": [{
                                "stack_type": "IPV4_IPV6",
                                "services_secondary_range_name": (
                                    "${google_compute_subnetwork.default"
                                    ".secondary_ip_range[0].range_name}"
                                ),
                                "cluster_secondary_range_name": (
                                    "${google_compute_subnetwork.default"
                                    ".secondary_ip_range[1].range_name}"
                                ),
                            }],
                            "deletion_protection": False,
                        }
                    }]
                },
            ]
        })
