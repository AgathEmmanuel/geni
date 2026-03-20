from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class NetworkingTemplate(Template):
    """Generates VPC networking infrastructure including subnets, firewall rules,
    Cloud Router, and Cloud NAT for private GKE clusters and compute instances."""

    def render(self, context: RenderContext) -> list[GeneratedFile]:
        params = context.params
        project = params["project"]
        region = params["region"]
        env = params["environment"]
        network_name = params["network_name"]
        subnet_cidr = params["subnet_cidr"]
        pods_cidr = params["pods_cidr"]
        services_cidr = params["services_cidr"]

        subnet_name = f"{network_name}-subnet"
        router_name = f"{network_name}-router"
        nat_name = f"{network_name}-nat"

        resources = {
            "resource": {
                "google_compute_network": {
                    network_name: {
                        "name": network_name,
                        "project": project,
                        "auto_create_subnetworks": False,
                        "routing_mode": "REGIONAL",
                        "delete_default_routes_on_create": False,
                    }
                },
                "google_compute_subnetwork": {
                    subnet_name: {
                        "name": subnet_name,
                        "project": project,
                        "region": region,
                        "network": f"${{google_compute_network.{network_name}.id}}",
                        "ip_cidr_range": subnet_cidr,
                        "private_ip_google_access": True,
                        "secondary_ip_range": [
                            {
                                "range_name": f"{env}-pods",
                                "ip_cidr_range": pods_cidr,
                            },
                            {
                                "range_name": f"{env}-services",
                                "ip_cidr_range": services_cidr,
                            },
                        ],
                        "log_config": {
                            "aggregation_interval": "INTERVAL_5_SEC",
                            "flow_sampling": 0.5,
                            "metadata": "INCLUDE_ALL_METADATA",
                        },
                    }
                },
                "google_compute_firewall": {
                    f"{network_name}-allow-ssh": {
                        "name": f"{network_name}-allow-ssh",
                        "project": project,
                        "network": f"${{google_compute_network.{network_name}.id}}",
                        "priority": 1000,
                        "direction": "INGRESS",
                        "source_ranges": ["0.0.0.0/0"],
                        "target_tags": ["allow-ssh"],
                        "allow": [
                            {
                                "protocol": "tcp",
                                "ports": ["22"],
                            }
                        ],
                    },
                    f"{network_name}-allow-internal": {
                        "name": f"{network_name}-allow-internal",
                        "project": project,
                        "network": f"${{google_compute_network.{network_name}.id}}",
                        "priority": 1000,
                        "direction": "INGRESS",
                        "source_ranges": [subnet_cidr, pods_cidr, services_cidr],
                        "allow": [
                            {"protocol": "tcp", "ports": ["0-65535"]},
                            {"protocol": "udp", "ports": ["0-65535"]},
                            {"protocol": "icmp"},
                        ],
                    },
                    f"{network_name}-allow-health-check": {
                        "name": f"{network_name}-allow-health-check",
                        "project": project,
                        "network": f"${{google_compute_network.{network_name}.id}}",
                        "priority": 1000,
                        "direction": "INGRESS",
                        "source_ranges": [
                            "130.211.0.0/22",
                            "35.191.0.0/16",
                        ],
                        "allow": [
                            {"protocol": "tcp"},
                        ],
                    },
                },
                "google_compute_router": {
                    router_name: {
                        "name": router_name,
                        "project": project,
                        "region": region,
                        "network": f"${{google_compute_network.{network_name}.id}}",
                    }
                },
                "google_compute_router_nat": {
                    nat_name: {
                        "name": nat_name,
                        "project": project,
                        "region": region,
                        "router": f"${{google_compute_router.{router_name}.name}}",
                        "nat_ip_allocate_option": "AUTO_ONLY",
                        "source_subnetwork_ip_ranges_to_nat": "ALL_SUBNETWORKS_ALL_IP_RANGES",
                        "log_config": {
                            "enable": True,
                            "filter": "ERRORS_ONLY",
                        },
                    }
                },
            }
        }

        return TerraformJSON("networking.tf.json", content=resources)
