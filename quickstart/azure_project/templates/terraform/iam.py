from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class IAM(Template):
    """Azure IAM: managed identities, role assignments, federated credentials."""

    def render(self, context: RenderContext) -> list[GeneratedFile]:
        p = context.params
        project = p["project"]
        env = p["environment"]
        location = p["location"]
        rg_name = p["resource_group_name"]
        subscription_id = p["subscription_id"]
        cluster_name = p["cluster_name"]
        app_namespace = p["app_namespace"]

        prefix = f"{project}-{env}"
        scope = f"/subscriptions/{subscription_id}/resourceGroups/{rg_name}"

        content = {
            "resource": {
                # ------------------------------------------------------------
                # User Assigned Managed Identities
                # ------------------------------------------------------------
                "azurerm_user_assigned_identity": {
                    "aks": {
                        "name": f"id-aks-{prefix}",
                        "location": location,
                        "resource_group_name": "${azurerm_resource_group.main.name}",
                        "tags": {
                            "project": project,
                            "environment": env,
                        },
                    },
                    "app_workload": {
                        "name": f"id-app-{prefix}",
                        "location": location,
                        "resource_group_name": "${azurerm_resource_group.main.name}",
                        "tags": {
                            "project": project,
                            "environment": env,
                        },
                    },
                    "vm": {
                        "name": f"id-vm-{prefix}",
                        "location": location,
                        "resource_group_name": "${azurerm_resource_group.main.name}",
                        "tags": {
                            "project": project,
                            "environment": env,
                        },
                    },
                },
                # ------------------------------------------------------------
                # Role Assignments
                # ------------------------------------------------------------
                "azurerm_role_assignment": {
                    "app_storage_blob_contributor": {
                        "scope": "${azurerm_storage_account.main.id}",
                        "role_definition_name": "Storage Blob Data Contributor",
                        "principal_id": "${azurerm_user_assigned_identity.app_workload.principal_id}",
                        "skip_service_principal_aad_check": True,
                    },
                    "aks_cluster_admin": {
                        "scope": "${azurerm_kubernetes_cluster.main.id}",
                        "role_definition_name": "Azure Kubernetes Service Cluster Admin Role",
                        "principal_id": "${azurerm_user_assigned_identity.aks.principal_id}",
                        "skip_service_principal_aad_check": True,
                    },
                    "vm_contributor": {
                        "scope": scope,
                        "role_definition_name": "Virtual Machine Contributor",
                        "principal_id": "${azurerm_user_assigned_identity.vm.principal_id}",
                        "skip_service_principal_aad_check": True,
                    },
                    "vm_storage_blob_reader": {
                        "scope": "${azurerm_storage_account.main.id}",
                        "role_definition_name": "Storage Blob Data Reader",
                        "principal_id": "${azurerm_user_assigned_identity.vm.principal_id}",
                        "skip_service_principal_aad_check": True,
                    },
                },
                # ------------------------------------------------------------
                # Federated Identity Credential for AKS Workload Identity
                # ------------------------------------------------------------
                "azurerm_federated_identity_credential": {
                    "app_workload": {
                        "name": f"fic-app-{prefix}",
                        "resource_group_name": "${azurerm_resource_group.main.name}",
                        "parent_id": "${azurerm_user_assigned_identity.app_workload.id}",
                        "audience": ["api://AzureADTokenExchange"],
                        "issuer": "${azurerm_kubernetes_cluster.main.oidc_issuer_url}",
                        "subject": f"system:serviceaccount:{app_namespace}:{app_namespace}-sa",
                    },
                },
            },
        }

        return [TerraformJSON("iam.tf.json.tf.json", content)]
