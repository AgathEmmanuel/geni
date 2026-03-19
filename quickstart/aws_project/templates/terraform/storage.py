from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class StorageTemplate(Template):
    """Generates S3 buckets with versioning, encryption, public access blocking,
    and bucket policies for service role access."""

    def render(self, context: RenderContext) -> GeneratedFile:
        params = context.params
        project = params["project"]
        env = params["environment"]
        buckets = params.get("buckets", [])

        prefix = f"{project}-{env}"

        s3_buckets = {}
        versioning = {}
        encryption = {}
        public_access = {}
        bucket_policies = {}

        for bucket_cfg in buckets:
            name = bucket_cfg["name"]
            bucket_key = name.replace("-", "_")
            full_name = f"{prefix}-{name}"

            # S3 Bucket
            s3_buckets[bucket_key] = {
                "bucket": full_name,
                "force_destroy": True,
                "tags": {
                    "Name": full_name,
                    "Environment": env,
                    "Project": project,
                },
            }

            # Versioning
            versioning[bucket_key] = {
                "bucket": f"${{aws_s3_bucket.{bucket_key}.id}}",
                "versioning_configuration": {
                    "status": "Enabled" if bucket_cfg.get("versioning", False) else "Suspended",
                },
            }

            # Server-side encryption
            encryption[bucket_key] = {
                "bucket": f"${{aws_s3_bucket.{bucket_key}.id}}",
                "rule": {
                    "apply_server_side_encryption_by_default": {
                        "sse_algorithm": "aws:kms",
                    },
                    "bucket_key_enabled": True,
                },
            }

            # Public access block
            public_access[bucket_key] = {
                "bucket": f"${{aws_s3_bucket.{bucket_key}.id}}",
                "block_public_acls": True,
                "block_public_policy": True,
                "ignore_public_acls": True,
                "restrict_public_buckets": True,
            }

            # Bucket policy - allow access from EC2 and IRSA roles
            bucket_policies[bucket_key] = {
                "bucket": f"${{aws_s3_bucket.{bucket_key}.id}}",
                "policy": f'${{jsonencode({{'
                    f'"Version": "2012-10-17",'
                    f'"Statement": [{{'
                    f'"Effect": "Allow",'
                    f'"Principal": {{'
                    f'"AWS": ['
                    f'"${{aws_iam_role.ec2_instance.arn}}",'
                    f'"${{aws_iam_role.app_irsa.arn}}"'
                    f']'
                    f'}},'
                    f'"Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],'
                    f'"Resource": ['
                    f'"arn:aws:s3:::{full_name}",'
                    f'"arn:aws:s3:::{full_name}/*"'
                    f']'
                    f'}}]'
                    f'}})}}'
            }

        resources = {
            "resource": {
                "aws_s3_bucket": s3_buckets,
                "aws_s3_bucket_versioning": versioning,
                "aws_s3_bucket_server_side_encryption_configuration": encryption,
                "aws_s3_bucket_public_access_block": public_access,
                "aws_s3_bucket_policy": bucket_policies,
            }
        }

        return TerraformJSON(filename="storage", content=resources)
