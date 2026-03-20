from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class KubernetesTemplate(Template):
    """Generates an EKS cluster with a managed node group, core add-ons (vpc-cni,
    coredns, kube-proxy), OIDC provider for IRSA, and supporting data sources."""

    def render(self, context: RenderContext) -> GeneratedFile:
        params = context.params
        project = params["project"]
        region = params["region"]
        env = params["environment"]
        cluster_name = params["cluster_name"]
        instance_type = params["instance_type"]

        prefix = f"{project}-{env}"
        full_cluster_name = f"{prefix}-{cluster_name}"

        resources = {
            "data": {
                # --- TLS certificate for OIDC thumbprint ---
                "tls_certificate": {
                    "eks": {
                        "url": f"${{aws_eks_cluster.{cluster_name}.identity[0].oidc[0].issuer}}",
                    }
                },
            },
            "resource": {
                # --- EKS Cluster ---
                "aws_eks_cluster": {
                    cluster_name: {
                        "name": full_cluster_name,
                        "role_arn": "${aws_iam_role.eks_cluster.arn}",
                        "version": "1.29",
                        "vpc_config": {
                            "subnet_ids": [
                                "${aws_subnet.public_a.id}",
                                "${aws_subnet.public_b.id}",
                                "${aws_subnet.private_a.id}",
                                "${aws_subnet.private_b.id}",
                            ],
                            "security_group_ids": [
                                "${aws_security_group.eks.id}",
                            ],
                            "endpoint_private_access": True,
                            "endpoint_public_access": True,
                        },
                        "enabled_cluster_log_types": [
                            "api",
                            "audit",
                            "authenticator",
                            "controllerManager",
                            "scheduler",
                        ],
                        "depends_on": [
                            "aws_iam_role_policy_attachment.eks_cluster_policy",
                            "aws_iam_role_policy_attachment.eks_vpc_resource_controller",
                        ],
                        "tags": {
                            "Name": full_cluster_name,
                            "Environment": env,
                            "Project": project,
                        },
                    }
                },
                # --- EKS Managed Node Group ---
                "aws_eks_node_group": {
                    f"{cluster_name}_nodes": {
                        "cluster_name": f"${{aws_eks_cluster.{cluster_name}.name}}",
                        "node_group_name": f"{full_cluster_name}-nodes",
                        "node_role_arn": "${aws_iam_role.eks_node_group.arn}",
                        "subnet_ids": [
                            "${aws_subnet.private_a.id}",
                            "${aws_subnet.private_b.id}",
                        ],
                        "instance_types": [instance_type],
                        "ami_type": "AL2_x86_64",
                        "capacity_type": "ON_DEMAND",
                        "disk_size": 50,
                        "scaling_config": {
                            "desired_size": 2,
                            "min_size": 1,
                            "max_size": 4,
                        },
                        "update_config": {
                            "max_unavailable": 1,
                        },
                        "depends_on": [
                            "aws_iam_role_policy_attachment.eks_node_worker",
                            "aws_iam_role_policy_attachment.eks_node_cni",
                            "aws_iam_role_policy_attachment.eks_node_ecr",
                        ],
                        "tags": {
                            "Name": f"{full_cluster_name}-nodes",
                            "Environment": env,
                        },
                    }
                },
                # --- EKS Add-ons ---
                "aws_eks_addon": {
                    "vpc_cni": {
                        "cluster_name": f"${{aws_eks_cluster.{cluster_name}.name}}",
                        "addon_name": "vpc-cni",
                        "resolve_conflicts_on_update": "OVERWRITE",
                    },
                    "coredns": {
                        "cluster_name": f"${{aws_eks_cluster.{cluster_name}.name}}",
                        "addon_name": "coredns",
                        "resolve_conflicts_on_update": "OVERWRITE",
                        "depends_on": [f"aws_eks_node_group.{cluster_name}_nodes"],
                    },
                    "kube_proxy": {
                        "cluster_name": f"${{aws_eks_cluster.{cluster_name}.name}}",
                        "addon_name": "kube-proxy",
                        "resolve_conflicts_on_update": "OVERWRITE",
                    },
                },
                # --- OIDC Provider for IRSA ---
                "aws_iam_openid_connect_provider": {
                    "eks": {
                        "client_id_list": ["sts.amazonaws.com"],
                        "thumbprint_list": [
                            "${data.tls_certificate.eks.certificates[0].sha1_fingerprint}"
                        ],
                        "url": f"${{aws_eks_cluster.{cluster_name}.identity[0].oidc[0].issuer}}",
                        "tags": {
                            "Name": f"{full_cluster_name}-oidc",
                            "Environment": env,
                        },
                    }
                },
            },
        }

        return TerraformJSON(filename="kubernetes.tf.json", content=resources)
