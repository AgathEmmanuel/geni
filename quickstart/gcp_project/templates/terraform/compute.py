from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class ComputeTemplate(Template):
    """Generates a GCE instance with SSH access, a startup script for basic
    tooling, and proper service account attachment."""

    def render(self, context: RenderContext) -> GeneratedFile:
        params = context.params
        project = params["project"]
        zone = params["zone"]
        env = params["environment"]
        machine_type = params["machine_type"]
        network_name = params["network_name"]

        instance_name = f"{env}-bastion"
        compute_sa_name = f"{env}-compute"
        subnet_name = f"{network_name}-subnet"

        startup_script = """#!/bin/bash
set -euo pipefail

# Update packages
apt-get update -y
apt-get upgrade -y

# Install essential tools
apt-get install -y \\
    curl \\
    wget \\
    git \\
    jq \\
    unzip \\
    apt-transport-https \\
    ca-certificates \\
    gnupg \\
    lsb-release

# Install kubectl
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.29/deb/Release.key | gpg --dearmor -o /usr/share/keyrings/kubernetes-apt-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.29/deb/ /" > /etc/apt/sources.list.d/kubernetes.list
apt-get update -y
apt-get install -y kubectl

# Install cloud-sql-proxy
curl -o /usr/local/bin/cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.1/cloud-sql-proxy.linux.amd64
chmod +x /usr/local/bin/cloud-sql-proxy

echo "Startup script completed successfully" | logger
"""

        resources = {
            "resource": {
                "google_compute_instance": {
                    instance_name: {
                        "name": instance_name,
                        "project": project,
                        "zone": zone,
                        "machine_type": machine_type,
                        "tags": ["allow-ssh"],
                        "boot_disk": {
                            "initialize_params": {
                                "image": "debian-cloud/debian-12",
                                "size": 20,
                                "type": "pd-balanced",
                            }
                        },
                        "network_interface": {
                            "network": f"${{google_compute_network.{network_name}.id}}",
                            "subnetwork": f"${{google_compute_subnetwork.{subnet_name}.id}}",
                            "access_config": {},
                        },
                        "metadata": {
                            "enable-oslogin": "TRUE",
                        },
                        "metadata_startup_script": startup_script,
                        "service_account": {
                            "email": f"${{google_service_account.{compute_sa_name}.email}}",
                            "scopes": ["cloud-platform"],
                        },
                        "shielded_instance_config": {
                            "enable_secure_boot": True,
                            "enable_vtpm": True,
                            "enable_integrity_monitoring": True,
                        },
                        "labels": {
                            "environment": env,
                            "role": "bastion",
                            "managed_by": "geni",
                        },
                        "allow_stopping_for_update": True,
                    }
                }
            }
        }

        return TerraformJSON(name="compute", content=resources)
