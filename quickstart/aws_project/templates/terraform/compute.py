from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class ComputeTemplate(Template):
    """Generates an EC2 instance with a key pair, latest Amazon Linux 2023 AMI
    data source, Elastic IP, and basic user data for initial setup."""

    def render(self, context: RenderContext) -> GeneratedFile:
        params = context.params
        project = params["project"]
        env = params["environment"]
        instance_type = params["instance_type"]
        key_name = params["key_name"]

        prefix = f"{project}-{env}"

        user_data = """#!/bin/bash
set -euo pipefail

# Update system packages
dnf update -y

# Install common utilities
dnf install -y htop vim curl wget jq unzip

# Install AWS CLI v2 (if not already present)
if ! command -v aws &> /dev/null; then
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/tmp/awscliv2.zip"
    unzip -q /tmp/awscliv2.zip -d /tmp
    /tmp/aws/install
    rm -rf /tmp/aws /tmp/awscliv2.zip
fi

# Install PostgreSQL client
dnf install -y postgresql15

# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
rm -f kubectl

# Enable and start SSM agent
systemctl enable amazon-ssm-agent
systemctl start amazon-ssm-agent

echo "User data setup complete" | tee /var/log/user-data-complete.log
"""

        resources = {
            # --- Data source for latest Amazon Linux 2023 AMI ---
            "data": {
                "aws_ami": {
                    "amazon_linux_2023": {
                        "most_recent": True,
                        "owners": ["amazon"],
                        "filter": [
                            {
                                "name": "name",
                                "values": ["al2023-ami-*-x86_64"],
                            },
                            {
                                "name": "virtualization-type",
                                "values": ["hvm"],
                            },
                            {
                                "name": "architecture",
                                "values": ["x86_64"],
                            },
                        ],
                    }
                }
            },
            "resource": {
                # --- TLS Private Key (for generating a new key pair) ---
                "tls_private_key": {
                    "bastion": {
                        "algorithm": "RSA",
                        "rsa_bits": 4096,
                    }
                },
                # --- Key Pair ---
                "aws_key_pair": {
                    "bastion": {
                        "key_name": f"{prefix}-{key_name}",
                        "public_key": "${tls_private_key.bastion.public_key_openssh}",
                        "tags": {
                            "Name": f"{prefix}-{key_name}",
                            "Environment": env,
                        },
                    }
                },
                # --- EC2 Instance (Bastion / Jump Host) ---
                "aws_instance": {
                    "bastion": {
                        "ami": "${data.aws_ami.amazon_linux_2023.id}",
                        "instance_type": instance_type,
                        "subnet_id": "${aws_subnet.public_a.id}",
                        "vpc_security_group_ids": [
                            "${aws_security_group.bastion.id}",
                            "${aws_security_group.internal.id}",
                        ],
                        "key_name": "${aws_key_pair.bastion.key_name}",
                        "iam_instance_profile": "${aws_iam_instance_profile.ec2.name}",
                        "user_data": user_data,
                        "root_block_device": {
                            "volume_type": "gp3",
                            "volume_size": 30,
                            "encrypted": True,
                        },
                        "metadata_options": {
                            "http_endpoint": "enabled",
                            "http_tokens": "required",
                            "http_put_response_hop_limit": 2,
                        },
                        "tags": {
                            "Name": f"{prefix}-bastion",
                            "Environment": env,
                            "Project": project,
                        },
                    }
                },
                # --- Elastic IP for Bastion ---
                "aws_eip": {
                    "bastion": {
                        "instance": "${aws_instance.bastion.id}",
                        "domain": "vpc",
                        "tags": {
                            "Name": f"{prefix}-bastion-eip",
                            "Environment": env,
                        },
                    }
                },
                # --- Store private key in Secrets Manager ---
                "aws_secretsmanager_secret": {
                    "bastion_key": {
                        "name": f"{prefix}/bastion-ssh-key",
                        "description": "SSH private key for bastion host",
                        "tags": {
                            "Name": f"{prefix}-bastion-ssh-key",
                            "Environment": env,
                        },
                    }
                },
                "aws_secretsmanager_secret_version": {
                    "bastion_key": {
                        "secret_id": "${aws_secretsmanager_secret.bastion_key.id}",
                        "secret_string": "${tls_private_key.bastion.private_key_pem}",
                    }
                },
            },
        }

        return TerraformJSON(filename="compute.tf.json", content=resources)
