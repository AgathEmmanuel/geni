from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class Database(Template):
    """Azure Database for PostgreSQL Flexible Server with private networking."""

    def render(self, context: RenderContext) -> list[GeneratedFile]:
        p = context.params
        project = p["project"]
        env = p["environment"]
        location = p["location"]
        db_name = p["db_name"]
        db_user = p["db_user"]
        db_sku = p.get("db_sku", "B_Standard_B1ms")
        db_storage_mb = p.get("db_storage_mb", 32768)

        prefix = f"{project}-{env}"

        content = {
            "resource": {
                # ------------------------------------------------------------
                # Random Password for PostgreSQL admin
                # ------------------------------------------------------------
                "random_password": {
                    "db_admin": {
                        "length": 24,
                        "special": True,
                        "override_special": "!#$%&*()-_=+[]{}|:?,.",
                        "min_lower": 2,
                        "min_upper": 2,
                        "min_numeric": 2,
                        "min_special": 2,
                    }
                },
                # ------------------------------------------------------------
                # PostgreSQL Flexible Server
                # ------------------------------------------------------------
                "azurerm_postgresql_flexible_server": {
                    "main": {
                        "name": f"psql-{prefix}",
                        "resource_group_name": "${azurerm_resource_group.main.name}",
                        "location": "${azurerm_resource_group.main.location}",
                        "version": "15",
                        "delegated_subnet_id": "${azurerm_subnet.database.id}",
                        "private_dns_zone_id": "${azurerm_private_dns_zone.postgres.id}",
                        "administrator_login": db_user,
                        "administrator_password": "${random_password.db_admin.result}",
                        "sku_name": db_sku,
                        "storage_mb": db_storage_mb,
                        "backup_retention_days": 7,
                        "geo_redundant_backup_enabled": False,
                        "zone": "1",
                        "authentication": {
                            "active_directory_auth_enabled": False,
                            "password_auth_enabled": True,
                        },
                        "tags": {
                            "project": project,
                            "environment": env,
                        },
                        "depends_on": [
                            "azurerm_private_dns_zone_virtual_network_link.postgres",
                        ],
                    }
                },
                # ------------------------------------------------------------
                # PostgreSQL Database
                # ------------------------------------------------------------
                "azurerm_postgresql_flexible_server_database": {
                    "main": {
                        "name": db_name,
                        "server_id": "${azurerm_postgresql_flexible_server.main.id}",
                        "charset": "UTF8",
                        "collation": "en_US.utf8",
                    }
                },
                # ------------------------------------------------------------
                # PostgreSQL Server Configurations
                # ------------------------------------------------------------
                "azurerm_postgresql_flexible_server_configuration": {
                    "log_checkpoints": {
                        "server_id": "${azurerm_postgresql_flexible_server.main.id}",
                        "name": "log_checkpoints",
                        "value": "on",
                    },
                    "log_connections": {
                        "server_id": "${azurerm_postgresql_flexible_server.main.id}",
                        "name": "log_connections",
                        "value": "on",
                    },
                    "log_disconnections": {
                        "server_id": "${azurerm_postgresql_flexible_server.main.id}",
                        "name": "log_disconnections",
                        "value": "on",
                    },
                    "connection_throttling": {
                        "server_id": "${azurerm_postgresql_flexible_server.main.id}",
                        "name": "connection_throttle.enable",
                        "value": "on",
                    },
                    "pgaudit_log": {
                        "server_id": "${azurerm_postgresql_flexible_server.main.id}",
                        "name": "pgaudit.log",
                        "value": "ddl,role",
                    },
                },
            },
        }

        return [TerraformJSON("database.tf.json", content)]
