from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class Compute(Template):
    """Azure Compute: Linux VM with SSH key, public IP, NIC."""

    def render(self, context: RenderContext) -> list[GeneratedFile]:
        p = context.params
        project = p["project"]
        env = p["environment"]
        location = p["location"]
        vm_size = p["vm_size"]
        admin_username = p.get("admin_username", "azureadmin")

        prefix = f"{project}-{env}"

        cloud_init = """#!/bin/bash
apt-get update
apt-get install -y curl wget git jq unzip apt-transport-https ca-certificates
# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | bash
# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
# Install PostgreSQL client
apt-get install -y postgresql-client
"""

        content = {
            "resource": {
                # ------------------------------------------------------------
                # TLS Private Key for SSH
                # ------------------------------------------------------------
                "tls_private_key": {
                    "vm_ssh": {
                        "algorithm": "RSA",
                        "rsa_bits": 4096,
                    }
                },
                # ------------------------------------------------------------
                # Public IP for VM
                # ------------------------------------------------------------
                "azurerm_public_ip": {
                    "vm": {
                        "name": f"pip-vm-{prefix}",
                        "location": "${azurerm_resource_group.main.location}",
                        "resource_group_name": "${azurerm_resource_group.main.name}",
                        "allocation_method": "Static",
                        "sku": "Standard",
                        "tags": {
                            "project": project,
                            "environment": env,
                        },
                    }
                },
                # ------------------------------------------------------------
                # Network Interface
                # ------------------------------------------------------------
                "azurerm_network_interface": {
                    "vm": {
                        "name": f"nic-vm-{prefix}",
                        "location": "${azurerm_resource_group.main.location}",
                        "resource_group_name": "${azurerm_resource_group.main.name}",
                        "ip_configuration": [
                            {
                                "name": "internal",
                                "subnet_id": "${azurerm_subnet.bastion.id}",
                                "private_ip_address_allocation": "Dynamic",
                                "public_ip_address_id": "${azurerm_public_ip.vm.id}",
                            }
                        ],
                        "tags": {
                            "project": project,
                            "environment": env,
                        },
                    }
                },
                # ------------------------------------------------------------
                # NSG Association for VM NIC
                # ------------------------------------------------------------
                "azurerm_network_interface_security_group_association": {
                    "vm": {
                        "network_interface_id": "${azurerm_network_interface.vm.id}",
                        "network_security_group_id": "${azurerm_network_security_group.bastion.id}",
                    }
                },
                # ------------------------------------------------------------
                # Linux Virtual Machine
                # ------------------------------------------------------------
                "azurerm_linux_virtual_machine": {
                    "main": {
                        "name": f"vm-{prefix}",
                        "location": "${azurerm_resource_group.main.location}",
                        "resource_group_name": "${azurerm_resource_group.main.name}",
                        "size": vm_size,
                        "admin_username": admin_username,
                        "network_interface_ids": [
                            "${azurerm_network_interface.vm.id}",
                        ],
                        "admin_ssh_key": {
                            "username": admin_username,
                            "public_key": "${tls_private_key.vm_ssh.public_key_openssh}",
                        },
                        "os_disk": {
                            "name": f"osdisk-vm-{prefix}",
                            "caching": "ReadWrite",
                            "storage_account_type": "Standard_LRS",
                            "disk_size_gb": 30,
                        },
                        "source_image_reference": {
                            "publisher": "Canonical",
                            "offer": "0001-com-ubuntu-server-jammy",
                            "sku": "22_04-lts-gen2",
                            "version": "latest",
                        },
                        "identity": {
                            "type": "UserAssigned",
                            "identity_ids": [
                                "${azurerm_user_assigned_identity.vm.id}",
                            ],
                        },
                        "custom_data": "${base64encode(<<-EOF\n" + cloud_init + "EOF\n)}",
                        "tags": {
                            "project": project,
                            "environment": env,
                            "role": "bastion",
                        },
                    }
                },
            },
        }

        return [TerraformJSON("compute.tf.json.tf.json", content)]
