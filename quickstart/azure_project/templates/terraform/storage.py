from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class Storage(Template):
    """Azure Storage: storage account, containers, RBAC."""

    def render(self, context: RenderContext) -> list[GeneratedFile]:
        p = context.params
        project = p["project"]
        env = p["environment"]
        location = p["location"]
        storage_account_name = p["storage_account_name"]
        containers = p.get("containers", ["app-data", "app-logs"])

        # Build container resources
        container_resources = {}
        for container_name in containers:
            safe_name = container_name.replace("-", "_")
            container_resources[safe_name] = {
                "name": container_name,
                "storage_account_name": "${azurerm_storage_account.main.name}",
                "container_access_type": "private",
            }

        content = {
            "resource": {
                # ------------------------------------------------------------
                # Storage Account
                # ------------------------------------------------------------
                "azurerm_storage_account": {
                    "main": {
                        "name": storage_account_name,
                        "resource_group_name": "${azurerm_resource_group.main.name}",
                        "location": "${azurerm_resource_group.main.location}",
                        "account_tier": "Standard",
                        "account_replication_type": "LRS",
                        "account_kind": "StorageV2",
                        "min_tls_version": "TLS1_2",
                        "enable_https_traffic_only": True,
                        "allow_nested_items_to_be_public": False,
                        "network_rules": {
                            "default_action": "Deny",
                            "bypass": ["AzureServices"],
                            "virtual_network_subnet_ids": [
                                "${azurerm_subnet.default.id}",
                                "${azurerm_subnet.aks.id}",
                            ],
                        },
                        "blob_properties": {
                            "versioning_enabled": True,
                            "delete_retention_policy": {
                                "days": 7,
                            },
                            "container_delete_retention_policy": {
                                "days": 7,
                            },
                        },
                        "tags": {
                            "project": project,
                            "environment": env,
                        },
                    }
                },
                # ------------------------------------------------------------
                # Storage Containers
                # ------------------------------------------------------------
                "azurerm_storage_container": container_resources,
                # ------------------------------------------------------------
                # Role Assignment: app workload identity -> blob contributor
                # ------------------------------------------------------------
                "azurerm_role_assignment": {
                    "storage_app_workload": {
                        "scope": "${azurerm_storage_account.main.id}",
                        "role_definition_name": "Storage Blob Data Contributor",
                        "principal_id": "${azurerm_user_assigned_identity.app_workload.principal_id}",
                        "skip_service_principal_aad_check": True,
                    },
                },
            },
        }

        return [TerraformJSON("storage.tf.json.tf.json", content)]
