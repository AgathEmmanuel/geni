from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class NetworkingTemplate(Template):
    """Generates AWS VPC networking infrastructure including public/private subnets
    across two availability zones, internet gateway, NAT gateway, route tables,
    and security groups for bastion, internal, database, and EKS traffic."""

    def render(self, context: RenderContext) -> GeneratedFile:
        params = context.params
        project = params["project"]
        region = params["region"]
        env = params["environment"]
        vpc_cidr = params["vpc_cidr"]

        prefix = f"{project}-{env}"

        resources = {
            "resource": {
                # --- VPC ---
                "aws_vpc": {
                    "main": {
                        "cidr_block": vpc_cidr,
                        "enable_dns_support": True,
                        "enable_dns_hostnames": True,
                        "tags": {
                            "Name": f"{prefix}-vpc",
                            "Environment": env,
                            "Project": project,
                        },
                    }
                },
                # --- Internet Gateway ---
                "aws_internet_gateway": {
                    "main": {
                        "vpc_id": "${aws_vpc.main.id}",
                        "tags": {
                            "Name": f"{prefix}-igw",
                            "Environment": env,
                        },
                    }
                },
                # --- Subnets ---
                "aws_subnet": {
                    "public_a": {
                        "vpc_id": "${aws_vpc.main.id}",
                        "cidr_block": "10.0.1.0/24",
                        "availability_zone": f"{region}a",
                        "map_public_ip_on_launch": True,
                        "tags": {
                            "Name": f"{prefix}-public-a",
                            "Environment": env,
                            "kubernetes.io/role/elb": "1",
                            f"kubernetes.io/cluster/{project}-{env}-cluster": "shared",
                        },
                    },
                    "public_b": {
                        "vpc_id": "${aws_vpc.main.id}",
                        "cidr_block": "10.0.2.0/24",
                        "availability_zone": f"{region}b",
                        "map_public_ip_on_launch": True,
                        "tags": {
                            "Name": f"{prefix}-public-b",
                            "Environment": env,
                            "kubernetes.io/role/elb": "1",
                            f"kubernetes.io/cluster/{project}-{env}-cluster": "shared",
                        },
                    },
                    "private_a": {
                        "vpc_id": "${aws_vpc.main.id}",
                        "cidr_block": "10.0.10.0/24",
                        "availability_zone": f"{region}a",
                        "tags": {
                            "Name": f"{prefix}-private-a",
                            "Environment": env,
                            "kubernetes.io/role/internal-elb": "1",
                            f"kubernetes.io/cluster/{project}-{env}-cluster": "shared",
                        },
                    },
                    "private_b": {
                        "vpc_id": "${aws_vpc.main.id}",
                        "cidr_block": "10.0.11.0/24",
                        "availability_zone": f"{region}b",
                        "tags": {
                            "Name": f"{prefix}-private-b",
                            "Environment": env,
                            "kubernetes.io/role/internal-elb": "1",
                            f"kubernetes.io/cluster/{project}-{env}-cluster": "shared",
                        },
                    },
                },
                # --- Elastic IP for NAT Gateway ---
                "aws_eip": {
                    "nat": {
                        "domain": "vpc",
                        "tags": {
                            "Name": f"{prefix}-nat-eip",
                            "Environment": env,
                        },
                    }
                },
                # --- NAT Gateway ---
                "aws_nat_gateway": {
                    "main": {
                        "allocation_id": "${aws_eip.nat.id}",
                        "subnet_id": "${aws_subnet.public_a.id}",
                        "tags": {
                            "Name": f"{prefix}-nat",
                            "Environment": env,
                        },
                        "depends_on": ["aws_internet_gateway.main"],
                    }
                },
                # --- Route Tables ---
                "aws_route_table": {
                    "public": {
                        "vpc_id": "${aws_vpc.main.id}",
                        "route": [
                            {
                                "cidr_block": "0.0.0.0/0",
                                "gateway_id": "${aws_internet_gateway.main.id}",
                            }
                        ],
                        "tags": {
                            "Name": f"{prefix}-public-rt",
                            "Environment": env,
                        },
                    },
                    "private": {
                        "vpc_id": "${aws_vpc.main.id}",
                        "route": [
                            {
                                "cidr_block": "0.0.0.0/0",
                                "nat_gateway_id": "${aws_nat_gateway.main.id}",
                            }
                        ],
                        "tags": {
                            "Name": f"{prefix}-private-rt",
                            "Environment": env,
                        },
                    },
                },
                # --- Route Table Associations ---
                "aws_route_table_association": {
                    "public_a": {
                        "subnet_id": "${aws_subnet.public_a.id}",
                        "route_table_id": "${aws_route_table.public.id}",
                    },
                    "public_b": {
                        "subnet_id": "${aws_subnet.public_b.id}",
                        "route_table_id": "${aws_route_table.public.id}",
                    },
                    "private_a": {
                        "subnet_id": "${aws_subnet.private_a.id}",
                        "route_table_id": "${aws_route_table.private.id}",
                    },
                    "private_b": {
                        "subnet_id": "${aws_subnet.private_b.id}",
                        "route_table_id": "${aws_route_table.private.id}",
                    },
                },
                # --- Security Groups ---
                "aws_security_group": {
                    "bastion": {
                        "name": f"{prefix}-bastion-sg",
                        "description": "Security group for bastion host - allows SSH access",
                        "vpc_id": "${aws_vpc.main.id}",
                        "ingress": [
                            {
                                "description": "SSH from anywhere",
                                "from_port": 22,
                                "to_port": 22,
                                "protocol": "tcp",
                                "cidr_blocks": ["0.0.0.0/0"],
                            }
                        ],
                        "egress": [
                            {
                                "description": "Allow all outbound",
                                "from_port": 0,
                                "to_port": 0,
                                "protocol": "-1",
                                "cidr_blocks": ["0.0.0.0/0"],
                            }
                        ],
                        "tags": {
                            "Name": f"{prefix}-bastion-sg",
                            "Environment": env,
                        },
                    },
                    "internal": {
                        "name": f"{prefix}-internal-sg",
                        "description": "Security group for internal communication within VPC",
                        "vpc_id": "${aws_vpc.main.id}",
                        "ingress": [
                            {
                                "description": "All traffic from VPC",
                                "from_port": 0,
                                "to_port": 0,
                                "protocol": "-1",
                                "cidr_blocks": [vpc_cidr],
                            }
                        ],
                        "egress": [
                            {
                                "description": "Allow all outbound",
                                "from_port": 0,
                                "to_port": 0,
                                "protocol": "-1",
                                "cidr_blocks": ["0.0.0.0/0"],
                            }
                        ],
                        "tags": {
                            "Name": f"{prefix}-internal-sg",
                            "Environment": env,
                        },
                    },
                    "database": {
                        "name": f"{prefix}-db-sg",
                        "description": "Security group for RDS PostgreSQL - allows port 5432 from internal",
                        "vpc_id": "${aws_vpc.main.id}",
                        "ingress": [
                            {
                                "description": "PostgreSQL from internal SG",
                                "from_port": 5432,
                                "to_port": 5432,
                                "protocol": "tcp",
                                "security_groups": [
                                    "${aws_security_group.internal.id}"
                                ],
                            }
                        ],
                        "egress": [
                            {
                                "description": "Allow all outbound",
                                "from_port": 0,
                                "to_port": 0,
                                "protocol": "-1",
                                "cidr_blocks": ["0.0.0.0/0"],
                            }
                        ],
                        "tags": {
                            "Name": f"{prefix}-db-sg",
                            "Environment": env,
                        },
                    },
                    "eks": {
                        "name": f"{prefix}-eks-sg",
                        "description": "Security group for EKS cluster",
                        "vpc_id": "${aws_vpc.main.id}",
                        "ingress": [
                            {
                                "description": "Allow all traffic from VPC for EKS",
                                "from_port": 0,
                                "to_port": 0,
                                "protocol": "-1",
                                "cidr_blocks": [vpc_cidr],
                            }
                        ],
                        "egress": [
                            {
                                "description": "Allow all outbound",
                                "from_port": 0,
                                "to_port": 0,
                                "protocol": "-1",
                                "cidr_blocks": ["0.0.0.0/0"],
                            }
                        ],
                        "tags": {
                            "Name": f"{prefix}-eks-sg",
                            "Environment": env,
                        },
                    },
                },
            }
        }

        return TerraformJSON(filename="networking", content=resources)
