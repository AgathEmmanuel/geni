from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class Kubernetes(Template):
    """Azure Kubernetes Service (AKS) cluster with workload identity."""

    def render(self, context: RenderContext) -> list[GeneratedFile]:
        p = context.params
        project = p["project"]
        env = p["environment"]
        location = p["location"]
        cluster_name = p["cluster_name"]
        k8s_vm_size = p["k8s_vm_size"]
        k8s_node_count = p.get("k8s_node_count", 2)
        k8s_min_count = p.get("k8s_min_count", 1)
        k8s_max_count = p.get("k8s_max_count", 5)
        k8s_version = p.get("k8s_version", "1.28")

        prefix = f"{project}-{env}"

        content = {
            "resource": {
                # ------------------------------------------------------------
                # AKS Cluster
                # ------------------------------------------------------------
                "azurerm_kubernetes_cluster": {
                    "main": {
                        "name": f"aks-{prefix}",
                        "location": "${azurerm_resource_group.main.location}",
                        "resource_group_name": "${azurerm_resource_group.main.name}",
                        "dns_prefix": f"aks-{prefix}",
                        "kubernetes_version": k8s_version,
                        "sku_tier": "Free",
                        "oidc_issuer_enabled": True,
                        "workload_identity_enabled": True,
                        "default_node_pool": {
                            "name": "system",
                            "vm_size": k8s_vm_size,
                            "node_count": k8s_node_count,
                            "min_count": k8s_min_count,
                            "max_count": k8s_max_count,
                            "enable_auto_scaling": True,
                            "vnet_subnet_id": "${azurerm_subnet.aks.id}",
                            "os_disk_size_gb": 50,
                            "os_disk_type": "Managed",
                            "max_pods": 50,
                            "temporary_name_for_rotation": "tmpnodepool",
                            "tags": {
                                "project": project,
                                "environment": env,
                            },
                        },
                        "identity": {
                            "type": "UserAssigned",
                            "identity_ids": [
                                "${azurerm_user_assigned_identity.aks.id}",
                            ],
                        },
                        "network_profile": {
                            "network_plugin": "azure",
                            "network_policy": "calico",
                            "service_cidr": "172.16.0.0/16",
                            "dns_service_ip": "172.16.0.10",
                            "load_balancer_sku": "standard",
                            "outbound_type": "userAssignedNATGateway",
                        },
                        "key_vault_secrets_provider": {
                            "secret_rotation_enabled": True,
                            "secret_rotation_interval": "2m",
                        },
                        "tags": {
                            "project": project,
                            "environment": env,
                        },
                    }
                },
                # ------------------------------------------------------------
                # Role Assignments for AKS identity
                # ------------------------------------------------------------
                "azurerm_role_assignment": {
                    "aks_network_contributor": {
                        "scope": "${azurerm_subnet.aks.id}",
                        "role_definition_name": "Network Contributor",
                        "principal_id": "${azurerm_user_assigned_identity.aks.principal_id}",
                        "skip_service_principal_aad_check": True,
                    },
                    "aks_managed_identity_operator": {
                        "scope": "${azurerm_user_assigned_identity.app_workload.id}",
                        "role_definition_name": "Managed Identity Operator",
                        "principal_id": "${azurerm_kubernetes_cluster.main.kubelet_identity[0].object_id}",
                        "skip_service_principal_aad_check": True,
                    },
                },
            },
        }

        return [TerraformJSON("kubernetes.tf.json.tf.json", content)]
