# AWS Quickstart with Geni

This guide walks you through deploying a complete AWS infrastructure stack using **geni** -- an IaC compilation tool that transforms YAML targets into Terraform and Kubernetes artifacts using Python templates.

The stack includes: VPC networking, EKS cluster, RDS PostgreSQL, EC2 bastion host, S3 buckets, IAM roles with IRSA, and a sample Kubernetes application.

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Install Geni](#2-install-geni)
3. [Initial AWS Setup](#3-initial-aws-setup)
4. [Configure the Project](#4-configure-the-project)
5. [Compile with Geni](#5-compile-with-geni)
6. [Deploy Infrastructure](#6-deploy-infrastructure)
7. [Connect to EKS](#7-connect-to-eks)
8. [Deploy Sample App](#8-deploy-sample-app)
9. [SSH to EC2 Bastion](#9-ssh-to-ec2-bastion)
10. [Connect to RDS](#10-connect-to-rds)
11. [Day 2 Operations](#11-day-2-operations)
12. [Cleanup](#12-cleanup)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Prerequisites

Ensure the following tools are installed and configured:

| Tool | Minimum Version | Installation |
|------|----------------|-------------|
| AWS CLI | v2.x | [Install AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |
| Terraform | >= 1.5.0 | [Install Terraform](https://developer.hashicorp.com/terraform/install) |
| kubectl | >= 1.28 | [Install kubectl](https://kubernetes.io/docs/tasks/tools/) |
| Python | >= 3.10 | [Install Python](https://www.python.org/downloads/) |
| geni | latest | See [Install Geni](#2-install-geni) |

You also need:
- An **AWS account** with permissions to create VPCs, EKS, RDS, EC2, S3, IAM, and Secrets Manager resources
- **AWS credentials** configured (access key + secret key, or SSO)

Verify your tools:

```bash
aws --version
terraform --version
kubectl version --client
python3 --version
```

## 2. Install Geni

One-line install (Linux / macOS):

```bash
curl -fsSL https://raw.githubusercontent.com/AgathEmmanuel/geni/main/install.sh | sh
```

Or with pip / pipx:

```bash
pip install geni
# or
pipx install geni
```

Install from source (no PyPI needed):

```bash
# Automated: clones repo, creates venv, installs to ~/.local/bin/geni
GENI_INSTALL=source curl -fsSL https://raw.githubusercontent.com/AgathEmmanuel/geni/main/install.sh | sh
```

Or manually from a cloned repo:

```bash
git clone https://github.com/AgathEmmanuel/geni.git
cd geni
python3 -m venv .venv && source .venv/bin/activate
pip install .

# Or run directly without installing:
PYTHONPATH=src python3 -m geni --version
```

Verify the installation:

```bash
geni --version
```

## 3. Initial AWS Setup

### Configure AWS credentials

```bash
aws configure
# AWS Access Key ID: <your-access-key>
# AWS Secret Access Key: <your-secret-key>
# Default region name: us-east-1
# Default output format: json
```

Or if using AWS SSO:

```bash
aws configure sso
aws sso login --profile your-profile
export AWS_PROFILE=your-profile
```

### Verify your identity

```bash
aws sts get-caller-identity
```

### Create the S3 bucket for Terraform state

```bash
aws s3api create-bucket \
  --bucket my-aws-project-tfstate \
  --region us-east-1

aws s3api put-bucket-versioning \
  --bucket my-aws-project-tfstate \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket my-aws-project-tfstate \
  --server-side-encryption-configuration '{
    "Rules": [
      {
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "aws:kms"
        },
        "BucketKeyEnabled": true
      }
    ]
  }'

aws s3api put-public-access-block \
  --bucket my-aws-project-tfstate \
  --public-access-block-configuration '{
    "BlockPublicAcls": true,
    "IgnorePublicAcls": true,
    "BlockPublicPolicy": true,
    "RestrictPublicBuckets": true
  }'
```

### Create the DynamoDB table for state locking

```bash
aws dynamodb create-table \
  --table-name my-aws-project-tflock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

Wait for the table to become active:

```bash
aws dynamodb wait table-exists --table-name my-aws-project-tflock
```

## 4. Configure the Project

Navigate to the project directory:

```bash
cd quickstart/aws_project
```

Edit `targets/dev.yml` to customize your deployment. Key values to update:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `project` | Project name (used in resource naming) | `my-aws-project` |
| `region` | AWS region | `us-east-1` |
| `vpc_cidr` | VPC CIDR block | `10.0.0.0/16` |
| `db_instance_class` | RDS instance size | `db.t3.medium` |
| `db_name` | Database name | `appdb` |
| `db_user` | Database master username | `appuser` |
| `instance_type` | EC2 / EKS node instance type | `t3.medium` |
| `cluster_name` | EKS cluster name suffix | `dev-cluster` |

Also update the backend configuration in the `backend` resource to match the S3 bucket and DynamoDB table you created in Step 3.

## 5. Compile with Geni

From the `aws_project` directory, compile the dev target:

```bash
geni compile -t dev
```

This will generate Terraform JSON files and Kubernetes manifests in the `compiled/dev/` directory:

```
compiled/dev/
├── backend.tf
├── provider.tf
├── networking.tf.json
├── iam.tf.json
├── storage.tf.json
├── compute.tf.json
├── database.tf.json
├── kubernetes.tf.json
├── outputs.tf.json
└── sample-app.yml
```

Inspect the generated files to verify they match your expectations:

```bash
ls -la compiled/dev/
cat compiled/dev/networking.tf.json | python3 -m json.tool | head -50
```

## 6. Deploy Infrastructure

### Initialize Terraform

```bash
cd compiled/dev
terraform init
```

Expected output: "Terraform has been successfully initialized!"

### Review the plan

```bash
terraform plan -out=tfplan
```

Review the output carefully. For a fresh deployment, expect approximately 50-60 resources to be created including:
- 1 VPC, 4 subnets, 1 internet gateway, 1 NAT gateway
- 4 security groups, 2 route tables, 4 route table associations
- 4+ IAM roles with policy attachments
- 3 S3 buckets with versioning, encryption, and access policies
- 1 EC2 instance with EIP
- 1 RDS PostgreSQL instance
- 1 EKS cluster with node group and add-ons
- Secrets Manager secrets for credentials

### Apply the plan

```bash
terraform apply tfplan
```

This will take approximately 15-25 minutes. The EKS cluster and RDS instance are the longest-running resources.

### Save important outputs

```bash
terraform output -json > ../terraform-outputs.json
```

## 7. Connect to EKS

Update your kubeconfig to connect to the EKS cluster:

```bash
aws eks update-kubeconfig \
  --name my-aws-project-dev-dev-cluster \
  --region us-east-1 \
  --alias dev-cluster
```

Verify connectivity:

```bash
kubectl cluster-info
kubectl get nodes
kubectl get namespaces
```

You should see the managed node group nodes in `Ready` state.

## 8. Deploy Sample App

Apply the generated Kubernetes manifests:

```bash
kubectl apply -f compiled/dev/sample-app.yml
```

Verify the deployment:

```bash
kubectl -n sample-app get all
kubectl -n sample-app get configmap sample-app-config -o yaml
kubectl -n sample-app get serviceaccount sample-app -o yaml
```

Wait for pods to be ready:

```bash
kubectl -n sample-app wait --for=condition=ready pod -l app.kubernetes.io/name=sample-app --timeout=120s
```

Check pod logs:

```bash
kubectl -n sample-app logs -l app.kubernetes.io/name=sample-app --tail=20
```

### Test the service

Port-forward to test locally:

```bash
kubectl -n sample-app port-forward svc/sample-app 8080:80
```

Then in another terminal:

```bash
curl http://localhost:8080
```

## 9. SSH to EC2 Bastion

### Retrieve the SSH private key from Secrets Manager

```bash
aws secretsmanager get-secret-value \
  --secret-id my-aws-project-dev/bastion-ssh-key \
  --query SecretString \
  --output text > bastion-key.pem

chmod 600 bastion-key.pem
```

### Get the bastion public IP

```bash
BASTION_IP=$(terraform -chdir=compiled/dev output -raw bastion_public_ip)
echo "Bastion IP: ${BASTION_IP}"
```

### Connect via SSH

```bash
ssh -i bastion-key.pem ec2-user@${BASTION_IP}
```

### Alternative: Connect via SSM (no SSH key needed)

```bash
INSTANCE_ID=$(terraform -chdir=compiled/dev output -raw bastion_instance_id)
aws ssm start-session --target ${INSTANCE_ID}
```

## 10. Connect to RDS

### Retrieve database credentials from Secrets Manager

```bash
DB_CREDS=$(aws secretsmanager get-secret-value \
  --secret-id my-aws-project-dev/db-credentials \
  --query SecretString \
  --output text)

DB_HOST=$(echo $DB_CREDS | python3 -c "import sys,json; print(json.load(sys.stdin)['host'])")
DB_PORT=$(echo $DB_CREDS | python3 -c "import sys,json; print(json.load(sys.stdin)['port'])")
DB_USER=$(echo $DB_CREDS | python3 -c "import sys,json; print(json.load(sys.stdin)['username'])")
DB_PASS=$(echo $DB_CREDS | python3 -c "import sys,json; print(json.load(sys.stdin)['password'])")
DB_NAME=$(echo $DB_CREDS | python3 -c "import sys,json; print(json.load(sys.stdin)['dbname'])")
```

### Connect through the bastion host

Since RDS is in a private subnet, connect through the bastion using an SSH tunnel:

```bash
# Open SSH tunnel in the background
ssh -i bastion-key.pem -N -L 5432:${DB_HOST}:${DB_PORT} ec2-user@${BASTION_IP} &

# Connect to PostgreSQL through the tunnel
PGPASSWORD=${DB_PASS} psql -h 127.0.0.1 -p 5432 -U ${DB_USER} -d ${DB_NAME}
```

### Verify database connectivity

Once connected via psql:

```sql
SELECT version();
\l
\dt
\q
```

### Kill the SSH tunnel when done

```bash
kill %1
```

## 11. Day 2 Operations

### Scaling the EKS node group

Edit `targets/dev.yml` and update the scaling config, then recompile and apply:

```bash
geni compile -t dev
cd compiled/dev
terraform plan -out=tfplan
terraform apply tfplan
```

### Adding a new S3 bucket

Add a new bucket entry under `storage.params.buckets` in `targets/dev.yml`:

```yaml
buckets:
  - name: app-assets
    versioning: true
  - name: app-backups
    versioning: true
  - name: app-uploads
    versioning: false
  - name: app-logs        # new bucket
    versioning: false
```

Then recompile and apply.

### Creating a new target environment (staging)

Copy the dev target and modify values:

```bash
cp targets/dev.yml targets/staging.yml
```

Edit `targets/staging.yml`:
- Change `metadata.name` to `staging`
- Update `environment` to `staging`
- Adjust instance types, CIDR ranges, and database sizing as needed
- Update the backend key to `staging/terraform.tfstate`

Compile and deploy:

```bash
geni compile -t staging
cd compiled/staging
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

### Updating Kubernetes manifests

After modifying `targets/dev.yml`, recompile and reapply:

```bash
geni compile -t dev
kubectl apply -f compiled/dev/sample-app.yml
```

### Viewing resource state

```bash
cd compiled/dev
terraform state list
terraform state show aws_eks_cluster.dev-cluster
terraform state show aws_db_instance.main
```

## 12. Cleanup

### Remove Kubernetes resources first

```bash
kubectl delete -f compiled/dev/sample-app.yml
```

### Destroy all Terraform-managed infrastructure

```bash
cd compiled/dev
terraform destroy
```

Type `yes` when prompted. This will take 10-15 minutes.

### Delete the Terraform state backend (optional)

Only do this if you are completely done with the project:

```bash
# Empty and delete the state bucket
aws s3 rm s3://my-aws-project-tfstate --recursive
aws s3api delete-bucket --bucket my-aws-project-tfstate --region us-east-1

# Delete the DynamoDB lock table
aws dynamodb delete-table --table-name my-aws-project-tflock --region us-east-1
```

### Clean up local files

```bash
rm -f bastion-key.pem
rm -rf compiled/dev/.terraform
rm -f compiled/dev/tfplan
rm -f compiled/dev/terraform-outputs.json
```

## 13. Troubleshooting

### Geni compilation fails

**Symptom**: `geni compile -t dev` returns an error.

```bash
# Verify .geni.yml exists and is valid
cat .geni.yml

# Check target YAML syntax
python3 -c "import yaml; yaml.safe_load(open('targets/dev.yml'))"

# Run with verbose logging
geni compile -t dev --verbose
```

### Terraform init fails with backend error

**Symptom**: `terraform init` fails with S3/DynamoDB access denied.

```bash
# Verify the state bucket exists
aws s3api head-bucket --bucket my-aws-project-tfstate

# Verify DynamoDB table exists
aws dynamodb describe-table --table-name my-aws-project-tflock

# Check your AWS identity and permissions
aws sts get-caller-identity
```

### EKS cluster unreachable

**Symptom**: `kubectl` commands fail with connection refused.

```bash
# Verify kubeconfig is set correctly
kubectl config current-context
kubectl config view --minify

# Re-generate kubeconfig
aws eks update-kubeconfig \
  --name my-aws-project-dev-dev-cluster \
  --region us-east-1

# Check cluster status
aws eks describe-cluster --name my-aws-project-dev-dev-cluster --query 'cluster.status'

# Verify your IAM identity matches the cluster creator
aws sts get-caller-identity
```

### EKS nodes not joining the cluster

**Symptom**: `kubectl get nodes` shows no nodes or nodes in `NotReady` state.

```bash
# Check node group status
aws eks describe-nodegroup \
  --cluster-name my-aws-project-dev-dev-cluster \
  --nodegroup-name my-aws-project-dev-dev-cluster-nodes

# Check for EC2 instances in the node group
aws ec2 describe-instances \
  --filters "Name=tag:eks:cluster-name,Values=my-aws-project-dev-dev-cluster" \
  --query 'Reservations[].Instances[].{ID:InstanceId,State:State.Name,Type:InstanceType}'

# Check VPC CNI add-on
aws eks describe-addon \
  --cluster-name my-aws-project-dev-dev-cluster \
  --addon-name vpc-cni
```

### RDS connection issues

**Symptom**: Cannot connect to PostgreSQL through the bastion.

```bash
# Verify RDS instance is available
aws rds describe-db-instances \
  --db-instance-identifier my-aws-project-dev-postgres \
  --query 'DBInstances[0].DBInstanceStatus'

# Verify security group allows traffic
aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=my-aws-project-dev-db-sg" \
  --query 'SecurityGroups[0].IpPermissions'

# Test connectivity from bastion (SSH in first)
ssh -i bastion-key.pem ec2-user@${BASTION_IP}
nc -zv <rds-endpoint> 5432
```

### Terraform apply times out

**Symptom**: Resources take too long or time out during creation.

```bash
# EKS clusters typically take 10-15 minutes
# RDS instances typically take 5-10 minutes
# NAT Gateways typically take 2-5 minutes

# Check resource status directly
aws eks describe-cluster --name my-aws-project-dev-dev-cluster --query 'cluster.status'
aws rds describe-db-instances --db-instance-identifier my-aws-project-dev-postgres --query 'DBInstances[0].DBInstanceStatus'

# If stuck, check CloudTrail for errors
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=CreateCluster \
  --max-results 5
```

### IAM / IRSA issues

**Symptom**: Pods cannot access S3 or RDS using the service account.

```bash
# Verify the OIDC provider is configured
aws eks describe-cluster \
  --name my-aws-project-dev-dev-cluster \
  --query 'cluster.identity.oidc.issuer'

aws iam list-open-id-connect-providers

# Verify the service account annotation
kubectl -n sample-app get sa sample-app -o jsonpath='{.metadata.annotations.eks\.amazonaws\.com/role-arn}'

# Test from inside a pod
kubectl -n sample-app exec -it deploy/sample-app -- env | grep AWS
kubectl -n sample-app exec -it deploy/sample-app -- aws sts get-caller-identity
```
