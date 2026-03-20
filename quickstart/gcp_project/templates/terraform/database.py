from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class DatabaseTemplate(Template):
    """Generates Cloud SQL PostgreSQL instance with private networking,
    automated backups, and secure password generation."""

    def render(self, context: RenderContext) -> GeneratedFile:
        params = context.params
        project = params["project"]
        region = params["region"]
        env = params["environment"]
        db_instance_name = params["db_instance_name"]
        db_name = params["db_name"]
        db_user = params["db_user"]
        network_name = params["network_name"]

        private_ip_name = f"{env}-sql-private-ip"
        connection_name = f"{env}-sql-vpc-connection"
        password_name = f"{db_instance_name}_password"

        resources = {
            "resource": {
                "google_compute_global_address": {
                    private_ip_name: {
                        "name": private_ip_name,
                        "project": project,
                        "purpose": "VPC_PEERING",
                        "address_type": "INTERNAL",
                        "prefix_length": 16,
                        "network": f"${{google_compute_network.{network_name}.id}}",
                    }
                },
                "google_service_networking_connection": {
                    connection_name: {
                        "network": f"${{google_compute_network.{network_name}.id}}",
                        "service": "servicenetworking.googleapis.com",
                        "reserved_peering_ranges": [
                            f"${{google_compute_global_address.{private_ip_name}.name}}"
                        ],
                    }
                },
                "random_password": {
                    password_name: {
                        "length": 24,
                        "special": True,
                        "override_special": "!#$%*()-_=+[]{}:?",
                    }
                },
                "google_sql_database_instance": {
                    db_instance_name: {
                        "name": db_instance_name,
                        "project": project,
                        "region": region,
                        "database_version": "POSTGRES_15",
                        "deletion_protection": False,
                        "depends_on": [
                            f"google_service_networking_connection.{connection_name}"
                        ],
                        "settings": {
                            "tier": "db-custom-2-7680",
                            "availability_type": "ZONAL",
                            "disk_size": 20,
                            "disk_type": "PD_SSD",
                            "disk_autoresize": True,
                            "disk_autoresize_limit": 100,
                            "ip_configuration": {
                                "ipv4_enabled": False,
                                "private_network": f"${{google_compute_network.{network_name}.id}}",
                                "require_ssl": False,
                            },
                            "backup_configuration": {
                                "enabled": True,
                                "start_time": "03:00",
                                "point_in_time_recovery_enabled": True,
                                "backup_retention_settings": {
                                    "retained_backups": 7,
                                    "retention_unit": "COUNT",
                                },
                                "transaction_log_retention_days": 7,
                            },
                            "maintenance_window": {
                                "day": 7,
                                "hour": 4,
                                "update_track": "stable",
                            },
                            "insights_config": {
                                "query_insights_enabled": True,
                                "query_plans_per_minute": 5,
                                "query_string_length": 1024,
                                "record_application_tags": True,
                                "record_client_address": True,
                            },
                            "database_flags": [
                                {
                                    "name": "log_checkpoints",
                                    "value": "on",
                                },
                                {
                                    "name": "log_connections",
                                    "value": "on",
                                },
                                {
                                    "name": "log_disconnections",
                                    "value": "on",
                                },
                                {
                                    "name": "log_lock_waits",
                                    "value": "on",
                                },
                            ],
                            "user_labels": {
                                "environment": env,
                                "managed_by": "geni",
                            },
                        },
                    }
                },
                "google_sql_database": {
                    db_name: {
                        "name": db_name,
                        "project": project,
                        "instance": f"${{google_sql_database_instance.{db_instance_name}.name}}",
                        "charset": "UTF8",
                        "collation": "en_US.UTF8",
                    }
                },
                "google_sql_user": {
                    db_user: {
                        "name": db_user,
                        "project": project,
                        "instance": f"${{google_sql_database_instance.{db_instance_name}.name}}",
                        "password": f"${{random_password.{password_name}.result}}",
                        "deletion_policy": "ABANDON",
                    }
                },
            }
        }

        return TerraformJSON("database.tf.json", content=resources)
