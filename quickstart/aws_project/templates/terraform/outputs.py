from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class OutputsTemplate(Template):
    """Generates Terraform outputs for cluster endpoint, VPC details, RDS
    connection info, EC2 public IP, S3 bucket ARNs, and security group IDs."""

    def render(self, context: RenderContext) -> GeneratedFile:
        params = context.params
        env = params["environment"]
        cluster_name = params["cluster_name"]

        resources = {
            "output": {
                # --- EKS Outputs ---
                "eks_cluster_name": {
                    "description": "EKS cluster name",
                    "value": f"${{aws_eks_cluster.{cluster_name}.name}}",
                },
                "eks_cluster_endpoint": {
                    "description": "EKS cluster API endpoint",
                    "value": f"${{aws_eks_cluster.{cluster_name}.endpoint}}",
                },
                "eks_cluster_certificate_authority": {
                    "description": "EKS cluster CA certificate (base64 encoded)",
                    "value": f"${{aws_eks_cluster.{cluster_name}.certificate_authority[0].data}}",
                    "sensitive": True,
                },
                "eks_cluster_version": {
                    "description": "EKS cluster Kubernetes version",
                    "value": f"${{aws_eks_cluster.{cluster_name}.version}}",
                },
                "eks_oidc_provider_arn": {
                    "description": "OIDC provider ARN for IRSA",
                    "value": "${aws_iam_openid_connect_provider.eks.arn}",
                },
                # --- VPC Outputs ---
                "vpc_id": {
                    "description": "VPC ID",
                    "value": "${aws_vpc.main.id}",
                },
                "public_subnet_ids": {
                    "description": "Public subnet IDs",
                    "value": [
                        "${aws_subnet.public_a.id}",
                        "${aws_subnet.public_b.id}",
                    ],
                },
                "private_subnet_ids": {
                    "description": "Private subnet IDs",
                    "value": [
                        "${aws_subnet.private_a.id}",
                        "${aws_subnet.private_b.id}",
                    ],
                },
                # --- RDS Outputs ---
                "rds_endpoint": {
                    "description": "RDS instance endpoint (host:port)",
                    "value": "${aws_db_instance.main.endpoint}",
                },
                "rds_address": {
                    "description": "RDS instance hostname",
                    "value": "${aws_db_instance.main.address}",
                },
                "rds_port": {
                    "description": "RDS instance port",
                    "value": "${aws_db_instance.main.port}",
                },
                "rds_credentials_secret_arn": {
                    "description": "Secrets Manager ARN for DB credentials",
                    "value": "${aws_secretsmanager_secret.db_credentials.arn}",
                },
                # --- EC2 Outputs ---
                "bastion_public_ip": {
                    "description": "Public IP of the bastion host",
                    "value": "${aws_eip.bastion.public_ip}",
                },
                "bastion_instance_id": {
                    "description": "Instance ID of the bastion host",
                    "value": "${aws_instance.bastion.id}",
                },
                "bastion_ssh_key_secret_arn": {
                    "description": "Secrets Manager ARN for bastion SSH key",
                    "value": "${aws_secretsmanager_secret.bastion_key.arn}",
                },
                # --- S3 Outputs ---
                "s3_bucket_app_assets_arn": {
                    "description": "ARN of app-assets S3 bucket",
                    "value": "${aws_s3_bucket.app_assets.arn}",
                },
                "s3_bucket_app_assets_name": {
                    "description": "Name of app-assets S3 bucket",
                    "value": "${aws_s3_bucket.app_assets.id}",
                },
                "s3_bucket_app_backups_arn": {
                    "description": "ARN of app-backups S3 bucket",
                    "value": "${aws_s3_bucket.app_backups.arn}",
                },
                "s3_bucket_app_backups_name": {
                    "description": "Name of app-backups S3 bucket",
                    "value": "${aws_s3_bucket.app_backups.id}",
                },
                "s3_bucket_app_uploads_arn": {
                    "description": "ARN of app-uploads S3 bucket",
                    "value": "${aws_s3_bucket.app_uploads.arn}",
                },
                "s3_bucket_app_uploads_name": {
                    "description": "Name of app-uploads S3 bucket",
                    "value": "${aws_s3_bucket.app_uploads.id}",
                },
                # --- Security Group Outputs ---
                "bastion_sg_id": {
                    "description": "Bastion security group ID",
                    "value": "${aws_security_group.bastion.id}",
                },
                "internal_sg_id": {
                    "description": "Internal security group ID",
                    "value": "${aws_security_group.internal.id}",
                },
                "database_sg_id": {
                    "description": "Database security group ID",
                    "value": "${aws_security_group.database.id}",
                },
                "eks_sg_id": {
                    "description": "EKS security group ID",
                    "value": "${aws_security_group.eks.id}",
                },
            }
        }

        return TerraformJSON(filename="outputs.tf.json", content=resources)
