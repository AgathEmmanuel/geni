from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class Networking(Template):
    """Azure networking: VNet, subnets, NSGs, NAT gateway, private DNS."""

    def render(self, context: RenderContext) -> list[GeneratedFile]:
        p = context.params
        project = p["project"]
        env = p["environment"]
        location = p["location"]
        rg_name = p["resource_group_name"]
        vnet_cidr = p["vnet_cidr"]
        subnet_default_cidr = p["subnet_default_cidr"]
        subnet_aks_cidr = p["subnet_aks_cidr"]
        subnet_database_cidr = p["subnet_database_cidr"]
        subnet_bastion_cidr = p["subnet_bastion_cidr"]

        prefix = f"{project}-{env}"

        content = {
            # ----------------------------------------------------------------
            # Resource Group
            # ----------------------------------------------------------------
            "resource": {
                "azurerm_resource_group": {
                    "main": {
                        "name": rg_name,
                        "location": location,
                        "tags": {
                            "project": project,
                            "environment": env,
                        },
                    }
                },
                # ------------------------------------------------------------
                # Virtual Network
                # ------------------------------------------------------------
                "azurerm_virtual_network": {
                    "main": {
                        "name": f"vnet-{prefix}",
                        "location": "${azurerm_resource_group.main.location}",
                        "resource_group_name": "${azurerm_resource_group.main.name}",
                        "address_space": [vnet_cidr],
                        "tags": {
                            "project": project,
                            "environment": env,
                        },
                    }
                },
                # ------------------------------------------------------------
                # Subnets
                # ------------------------------------------------------------
                "azurerm_subnet": {
                    "default": {
                        "name": "snet-default",
                        "resource_group_name": "${azurerm_resource_group.main.name}",
                        "virtual_network_name": "${azurerm_virtual_network.main.name}",
                        "address_prefixes": [subnet_default_cidr],
                    },
                    "aks": {
                        "name": "snet-aks",
                        "resource_group_name": "${azurerm_resource_group.main.name}",
                        "virtual_network_name": "${azurerm_virtual_network.main.name}",
                        "address_prefixes": [subnet_aks_cidr],
                    },
                    "database": {
                        "name": "snet-database",
                        "resource_group_name": "${azurerm_resource_group.main.name}",
                        "virtual_network_name": "${azurerm_virtual_network.main.name}",
                        "address_prefixes": [subnet_database_cidr],
                        "service_endpoints": ["Microsoft.Storage"],
                        "delegation": [
                            {
                                "name": "fs",
                                "service_delegation": {
                                    "name": "Microsoft.DBforPostgreSQL/flexibleServers",
                                    "actions": [
                                        "Microsoft.Network/virtualNetworks/subnets/join/action",
                                    ],
                                },
                            }
                        ],
                    },
                    "bastion": {
                        "name": "snet-bastion",
                        "resource_group_name": "${azurerm_resource_group.main.name}",
                        "virtual_network_name": "${azurerm_virtual_network.main.name}",
                        "address_prefixes": [subnet_bastion_cidr],
                    },
                },
                # ------------------------------------------------------------
                # Network Security Groups
                # ------------------------------------------------------------
                "azurerm_network_security_group": {
                    "bastion": {
                        "name": f"nsg-bastion-{prefix}",
                        "location": "${azurerm_resource_group.main.location}",
                        "resource_group_name": "${azurerm_resource_group.main.name}",
                        "security_rule": [
                            {
                                "name": "AllowSSHInbound",
                                "priority": 100,
                                "direction": "Inbound",
                                "access": "Allow",
                                "protocol": "Tcp",
                                "source_port_range": "*",
                                "destination_port_range": "22",
                                "source_address_prefix": "*",
                                "destination_address_prefix": "*",
                            },
                            {
                                "name": "DenyAllInbound",
                                "priority": 4096,
                                "direction": "Inbound",
                                "access": "Deny",
                                "protocol": "*",
                                "source_port_range": "*",
                                "destination_port_range": "*",
                                "source_address_prefix": "*",
                                "destination_address_prefix": "*",
                            },
                        ],
                        "tags": {
                            "project": project,
                            "environment": env,
                        },
                    },
                    "internal": {
                        "name": f"nsg-internal-{prefix}",
                        "location": "${azurerm_resource_group.main.location}",
                        "resource_group_name": "${azurerm_resource_group.main.name}",
                        "security_rule": [
                            {
                                "name": "AllowVNetInbound",
                                "priority": 100,
                                "direction": "Inbound",
                                "access": "Allow",
                                "protocol": "*",
                                "source_port_range": "*",
                                "destination_port_range": "*",
                                "source_address_prefix": "VirtualNetwork",
                                "destination_address_prefix": "VirtualNetwork",
                            },
                            {
                                "name": "DenyAllInbound",
                                "priority": 4096,
                                "direction": "Inbound",
                                "access": "Deny",
                                "protocol": "*",
                                "source_port_range": "*",
                                "destination_port_range": "*",
                                "source_address_prefix": "*",
                                "destination_address_prefix": "*",
                            },
                        ],
                        "tags": {
                            "project": project,
                            "environment": env,
                        },
                    },
                    "database": {
                        "name": f"nsg-database-{prefix}",
                        "location": "${azurerm_resource_group.main.location}",
                        "resource_group_name": "${azurerm_resource_group.main.name}",
                        "security_rule": [
                            {
                                "name": "AllowPostgreSQLFromVNet",
                                "priority": 100,
                                "direction": "Inbound",
                                "access": "Allow",
                                "protocol": "Tcp",
                                "source_port_range": "*",
                                "destination_port_range": "5432",
                                "source_address_prefix": "VirtualNetwork",
                                "destination_address_prefix": "*",
                            },
                            {
                                "name": "DenyAllInbound",
                                "priority": 4096,
                                "direction": "Inbound",
                                "access": "Deny",
                                "protocol": "*",
                                "source_port_range": "*",
                                "destination_port_range": "*",
                                "source_address_prefix": "*",
                                "destination_address_prefix": "*",
                            },
                        ],
                        "tags": {
                            "project": project,
                            "environment": env,
                        },
                    },
                },
                # ------------------------------------------------------------
                # NSG <-> Subnet Associations
                # ------------------------------------------------------------
                "azurerm_subnet_network_security_group_association": {
                    "bastion": {
                        "subnet_id": "${azurerm_subnet.bastion.id}",
                        "network_security_group_id": "${azurerm_network_security_group.bastion.id}",
                    },
                    "default": {
                        "subnet_id": "${azurerm_subnet.default.id}",
                        "network_security_group_id": "${azurerm_network_security_group.internal.id}",
                    },
                    "database": {
                        "subnet_id": "${azurerm_subnet.database.id}",
                        "network_security_group_id": "${azurerm_network_security_group.database.id}",
                    },
                },
                # ------------------------------------------------------------
                # NAT Gateway (for outbound connectivity)
                # ------------------------------------------------------------
                "azurerm_public_ip": {
                    "nat_gateway": {
                        "name": f"pip-nat-{prefix}",
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
                "azurerm_nat_gateway": {
                    "main": {
                        "name": f"ng-{prefix}",
                        "location": "${azurerm_resource_group.main.location}",
                        "resource_group_name": "${azurerm_resource_group.main.name}",
                        "sku_name": "Standard",
                        "idle_timeout_in_minutes": 10,
                        "tags": {
                            "project": project,
                            "environment": env,
                        },
                    }
                },
                "azurerm_nat_gateway_public_ip_association": {
                    "main": {
                        "nat_gateway_id": "${azurerm_nat_gateway.main.id}",
                        "public_ip_address_id": "${azurerm_public_ip.nat_gateway.id}",
                    }
                },
                "azurerm_subnet_nat_gateway_association": {
                    "default": {
                        "subnet_id": "${azurerm_subnet.default.id}",
                        "nat_gateway_id": "${azurerm_nat_gateway.main.id}",
                    },
                    "aks": {
                        "subnet_id": "${azurerm_subnet.aks.id}",
                        "nat_gateway_id": "${azurerm_nat_gateway.main.id}",
                    },
                },
                # ------------------------------------------------------------
                # Private DNS Zone for PostgreSQL
                # ------------------------------------------------------------
                "azurerm_private_dns_zone": {
                    "postgres": {
                        "name": f"{prefix}.postgres.database.azure.com",
                        "resource_group_name": "${azurerm_resource_group.main.name}",
                        "tags": {
                            "project": project,
                            "environment": env,
                        },
                    }
                },
                "azurerm_private_dns_zone_virtual_network_link": {
                    "postgres": {
                        "name": f"pdnslink-postgres-{prefix}",
                        "resource_group_name": "${azurerm_resource_group.main.name}",
                        "private_dns_zone_name": "${azurerm_private_dns_zone.postgres.name}",
                        "virtual_network_id": "${azurerm_virtual_network.main.id}",
                        "registration_enabled": False,
                        "tags": {
                            "project": project,
                            "environment": env,
                        },
                    }
                },
            },
        }

        return [TerraformJSON("networking.tf.json.tf.json", content)]
