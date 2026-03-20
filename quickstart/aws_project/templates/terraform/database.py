import json
from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class DatabaseTemplate(Template):
    """Generates an RDS PostgreSQL instance with a DB subnet group, random password,
    and credentials stored in AWS Secrets Manager."""

    def render(self, context: RenderContext) -> GeneratedFile:
        params = context.params
        project = params["project"]
        env = params["environment"]
        db_name = params["db_name"]
        db_user = params["db_user"]
        db_instance_class = params["db_instance_class"]

        prefix = f"{project}-{env}"

        resources = {
            "resource": {
                # --- Random password for the database ---
                "random_password": {
                    "db": {
                        "length": 32,
                        "special": True,
                        "override_special": "!#$%^&*()-_=+[]{}|:,.<>?",
                    }
                },
                # --- DB Subnet Group ---
                "aws_db_subnet_group": {
                    "main": {
                        "name": f"{prefix}-db-subnet-group",
                        "description": f"DB subnet group for {prefix}",
                        "subnet_ids": [
                            "${aws_subnet.private_a.id}",
                            "${aws_subnet.private_b.id}",
                        ],
                        "tags": {
                            "Name": f"{prefix}-db-subnet-group",
                            "Environment": env,
                        },
                    }
                },
                # --- RDS PostgreSQL Instance ---
                "aws_db_instance": {
                    "main": {
                        "identifier": f"{prefix}-postgres",
                        "engine": "postgres",
                        "engine_version": "15",
                        "instance_class": db_instance_class,
                        "allocated_storage": 20,
                        "max_allocated_storage": 100,
                        "storage_type": "gp3",
                        "storage_encrypted": True,
                        "db_name": db_name,
                        "username": db_user,
                        "password": "${random_password.db.result}",
                        "db_subnet_group_name": "${aws_db_subnet_group.main.name}",
                        "vpc_security_group_ids": [
                            "${aws_security_group.database.id}",
                        ],
                        "multi_az": False,
                        "publicly_accessible": False,
                        "skip_final_snapshot": True,
                        "deletion_protection": False,
                        "backup_retention_period": 7,
                        "backup_window": "03:00-04:00",
                        "maintenance_window": "sun:04:00-sun:05:00",
                        "performance_insights_enabled": True,
                        "monitoring_interval": 60,
                        "monitoring_role_arn": "${aws_iam_role.rds_monitoring.arn}",
                        "enabled_cloudwatch_logs_exports": [
                            "postgresql",
                            "upgrade",
                        ],
                        "tags": {
                            "Name": f"{prefix}-postgres",
                            "Environment": env,
                            "Project": project,
                        },
                    }
                },
                # --- RDS Enhanced Monitoring Role ---
                "aws_iam_role": {
                    "rds_monitoring": {
                        "name": f"{prefix}-rds-monitoring-role",
                        "assume_role_policy": json.dumps({
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Principal": {
                                        "Service": "monitoring.rds.amazonaws.com",
                                    },
                                    "Action": "sts:AssumeRole",
                                }
                            ],
                        }),
                        "tags": {
                            "Name": f"{prefix}-rds-monitoring-role",
                            "Environment": env,
                        },
                    }
                },
                "aws_iam_role_policy_attachment": {
                    "rds_monitoring": {
                        "role": "${aws_iam_role.rds_monitoring.name}",
                        "policy_arn": "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole",
                    }
                },
                # --- Secrets Manager for DB credentials ---
                "aws_secretsmanager_secret": {
                    "db_credentials": {
                        "name": f"{prefix}/db-credentials",
                        "description": f"Database credentials for {prefix}-postgres",
                        "tags": {
                            "Name": f"{prefix}-db-credentials",
                            "Environment": env,
                        },
                    }
                },
                "aws_secretsmanager_secret_version": {
                    "db_credentials": {
                        "secret_id": "${aws_secretsmanager_secret.db_credentials.id}",
                        "secret_string": '${jsonencode({'
                            '"username": aws_db_instance.main.username,'
                            '"password": random_password.db.result,'
                            '"host": aws_db_instance.main.address,'
                            '"port": aws_db_instance.main.port,'
                            '"dbname": aws_db_instance.main.db_name,'
                            '"engine": "postgres"'
                            '})}',
                    }
                },
            }
        }

        return TerraformJSON(filename="database.tf.json", content=resources)
