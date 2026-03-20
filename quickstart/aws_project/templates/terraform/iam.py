import json
from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class IAMTemplate(Template):
    """Generates IAM roles, policies, and instance profiles for EKS cluster,
    EKS node group, EC2 instances, and IRSA-based workload identity."""

    def render(self, context: RenderContext) -> GeneratedFile:
        params = context.params
        project = params["project"]
        env = params["environment"]
        cluster_name = params["cluster_name"]
        app_name = params["app_name"]
        app_namespace = params["app_namespace"]

        prefix = f"{project}-{env}"

        # Common assume role policy documents
        eks_assume_role = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "eks.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }

        ec2_assume_role = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "ec2.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }

        resources = {
            "resource": {
                # --- EKS Cluster Role ---
                "aws_iam_role": {
                    "eks_cluster": {
                        "name": f"{prefix}-eks-cluster-role",
                        "assume_role_policy": json.dumps(eks_assume_role),
                        "tags": {
                            "Name": f"{prefix}-eks-cluster-role",
                            "Environment": env,
                        },
                    },
                    "eks_node_group": {
                        "name": f"{prefix}-eks-node-role",
                        "assume_role_policy": json.dumps(ec2_assume_role),
                        "tags": {
                            "Name": f"{prefix}-eks-node-role",
                            "Environment": env,
                        },
                    },
                    "ec2_instance": {
                        "name": f"{prefix}-ec2-role",
                        "assume_role_policy": json.dumps(ec2_assume_role),
                        "tags": {
                            "Name": f"{prefix}-ec2-role",
                            "Environment": env,
                        },
                    },
                    "app_irsa": {
                        "name": f"{prefix}-{app_name}-irsa-role",
                        "assume_role_policy": json.dumps({
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Principal": {
                                        "Federated": "${aws_iam_openid_connect_provider.eks.arn}",
                                    },
                                    "Action": "sts:AssumeRoleWithWebIdentity",
                                    "Condition": {
                                        "StringEquals": {
                                            "${aws_iam_openid_connect_provider.eks.url}:sub":
                                                f"system:serviceaccount:{app_namespace}:{app_name}",
                                            "${aws_iam_openid_connect_provider.eks.url}:aud":
                                                "sts.amazonaws.com",
                                        }
                                    },
                                }
                            ],
                        }),
                        "tags": {
                            "Name": f"{prefix}-{app_name}-irsa-role",
                            "Environment": env,
                        },
                    },
                },
                # --- Policy Attachments ---
                "aws_iam_role_policy_attachment": {
                    "eks_cluster_policy": {
                        "role": "${aws_iam_role.eks_cluster.name}",
                        "policy_arn": "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy",
                    },
                    "eks_vpc_resource_controller": {
                        "role": "${aws_iam_role.eks_cluster.name}",
                        "policy_arn": "arn:aws:iam::aws:policy/AmazonEKSVPCResourceController",
                    },
                    "eks_node_worker": {
                        "role": "${aws_iam_role.eks_node_group.name}",
                        "policy_arn": "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
                    },
                    "eks_node_cni": {
                        "role": "${aws_iam_role.eks_node_group.name}",
                        "policy_arn": "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
                    },
                    "eks_node_ecr": {
                        "role": "${aws_iam_role.eks_node_group.name}",
                        "policy_arn": "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
                    },
                    "ec2_ssm": {
                        "role": "${aws_iam_role.ec2_instance.name}",
                        "policy_arn": "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
                    },
                    "app_irsa_policy": {
                        "role": "${aws_iam_role.app_irsa.name}",
                        "policy_arn": "${aws_iam_policy.app_workload.arn}",
                    },
                },
                # --- EC2 Instance Profile ---
                "aws_iam_instance_profile": {
                    "ec2": {
                        "name": f"{prefix}-ec2-instance-profile",
                        "role": "${aws_iam_role.ec2_instance.name}",
                    }
                },
                # --- App Workload Policy (S3 + RDS) ---
                "aws_iam_policy": {
                    "app_workload": {
                        "name": f"{prefix}-{app_name}-policy",
                        "description": f"Policy for {app_name} workload - S3 and RDS access",
                        "policy": json.dumps({
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": [
                                        "s3:GetObject",
                                        "s3:PutObject",
                                        "s3:ListBucket",
                                        "s3:DeleteObject",
                                    ],
                                    "Resource": [
                                        f"arn:aws:s3:::{prefix}-*",
                                        f"arn:aws:s3:::{prefix}-*/*",
                                    ],
                                },
                                {
                                    "Effect": "Allow",
                                    "Action": [
                                        "rds-db:connect",
                                    ],
                                    "Resource": [
                                        f"arn:aws:rds-db:*:*:dbuser:*/{app_name}",
                                    ],
                                },
                            ],
                        }),
                        "tags": {
                            "Name": f"{prefix}-{app_name}-policy",
                            "Environment": env,
                        },
                    }
                },
            }
        }

        return TerraformJSON(filename="iam.tf.json", content=resources)
