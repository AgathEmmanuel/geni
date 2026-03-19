from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class Outputs(Template):
    """Terraform outputs for all Azure resources."""

    def render(self, context: RenderContext) -> list[GeneratedFile]:
        content = {
            "output": {
                # AKS outputs
                "aks_cluster_name": {
                    "description": "Name of the AKS cluster",
                    "value": "${azurerm_kubernetes_cluster.main.name}",
                },
                "aks_kube_config_raw": {
                    "description": "Raw kubeconfig for the AKS cluster",
                    "value": "${azurerm_kubernetes_cluster.main.kube_config_raw}",
                    "sensitive": True,
                },
                "aks_host": {
                    "description": "AKS cluster API server host",
                    "value": "${azurerm_kubernetes_cluster.main.kube_config[0].host}",
                    "sensitive": True,
                },
                "aks_oidc_issuer_url": {
                    "description": "OIDC issuer URL for workload identity",
                    "value": "${azurerm_kubernetes_cluster.main.oidc_issuer_url}",
                },
                # Database outputs
                "db_fqdn": {
                    "description": "FQDN of the PostgreSQL Flexible Server",
                    "value": "${azurerm_postgresql_flexible_server.main.fqdn}",
                },
                "db_name": {
                    "description": "Name of the PostgreSQL database",
                    "value": "${azurerm_postgresql_flexible_server_database.main.name}",
                },
                "db_admin_username": {
                    "description": "PostgreSQL admin username",
                    "value": "${azurerm_postgresql_flexible_server.main.administrator_login}",
                },
                "db_admin_password": {
                    "description": "PostgreSQL admin password",
                    "value": "${random_password.db_admin.result}",
                    "sensitive": True,
                },
                # VM outputs
                "vm_public_ip": {
                    "description": "Public IP address of the bastion VM",
                    "value": "${azurerm_public_ip.vm.ip_address}",
                },
                "vm_ssh_private_key": {
                    "description": "SSH private key for the VM",
                    "value": "${tls_private_key.vm_ssh.private_key_pem}",
                    "sensitive": True,
                },
                "vm_admin_username": {
                    "description": "Admin username for the VM",
                    "value": "${azurerm_linux_virtual_machine.main.admin_username}",
                },
                # Networking outputs
                "resource_group_name": {
                    "description": "Name of the resource group",
                    "value": "${azurerm_resource_group.main.name}",
                },
                "vnet_id": {
                    "description": "ID of the virtual network",
                    "value": "${azurerm_virtual_network.main.id}",
                },
                "vnet_name": {
                    "description": "Name of the virtual network",
                    "value": "${azurerm_virtual_network.main.name}",
                },
                "subnet_default_id": {
                    "description": "ID of the default subnet",
                    "value": "${azurerm_subnet.default.id}",
                },
                "subnet_aks_id": {
                    "description": "ID of the AKS subnet",
                    "value": "${azurerm_subnet.aks.id}",
                },
                "subnet_database_id": {
                    "description": "ID of the database subnet",
                    "value": "${azurerm_subnet.database.id}",
                },
                # Storage outputs
                "storage_account_name": {
                    "description": "Name of the storage account",
                    "value": "${azurerm_storage_account.main.name}",
                },
                "storage_account_primary_access_key": {
                    "description": "Primary access key for the storage account",
                    "value": "${azurerm_storage_account.main.primary_access_key}",
                    "sensitive": True,
                },
                # Identity outputs
                "identity_aks_client_id": {
                    "description": "Client ID of the AKS managed identity",
                    "value": "${azurerm_user_assigned_identity.aks.client_id}",
                },
                "identity_app_workload_client_id": {
                    "description": "Client ID of the app workload managed identity",
                    "value": "${azurerm_user_assigned_identity.app_workload.client_id}",
                },
                "identity_vm_client_id": {
                    "description": "Client ID of the VM managed identity",
                    "value": "${azurerm_user_assigned_identity.vm.client_id}",
                },
            },
        }

        return [TerraformJSON("outputs.tf.json", content)]
