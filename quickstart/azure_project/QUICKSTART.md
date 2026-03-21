# Azure Quickstart - geni

This quickstart deploys a complete Azure development environment using **geni** to generate Terraform and Kubernetes artifacts from YAML targets into Terraform and Kubernetes artifacts.

## What Gets Deployed

- **Resource Group** with consistent tagging
- **Virtual Network** with four subnets (default, AKS, database, bastion)
- **Network Security Groups** with least-privilege rules
- **NAT Gateway** for outbound connectivity
- **Azure Kubernetes Service (AKS)** with workload identity and auto-scaling
- **Azure Database for PostgreSQL Flexible Server** (private networking)
- **Linux VM** (bastion host with SSH access)
- **Storage Account** with blob containers
- **Managed Identities** with RBAC role assignments
- **Sample Kubernetes application** manifests

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Azure CLI | >= 2.50 | [Install](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) |
| Terraform | >= 1.5 | [Install](https://developer.hashicorp.com/terraform/install) |
| kubectl | >= 1.28 | [Install](https://kubernetes.io/docs/tasks/tools/) |
| Python | >= 3.10 | [Install](https://www.python.org/downloads/) |
| geni | latest | `curl -fsSL https://raw.githubusercontent.com/AgathEmmanuel/geni/main/install.sh \| sh` |

You also need an active Azure subscription with permissions to create resources.

## 1. Install geni

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

## 2. Initial Azure Setup

### Log in to Azure

```bash
az login
```

Set your subscription (replace with your subscription ID):

```bash
az account set --subscription "YOUR_SUBSCRIPTION_ID"
```

### Create the Terraform state backend

Create a resource group and storage account to hold the Terraform state file:

```bash
# Variables
STATE_RG="rg-myazureproject-tfstate"
STATE_SA="stmyazureprojecttfstate"
STATE_CONTAINER="tfstate"
LOCATION="eastus"

# Create resource group for state
az group create \
  --name "$STATE_RG" \
  --location "$LOCATION"

# Create storage account for state
az storage account create \
  --name "$STATE_SA" \
  --resource-group "$STATE_RG" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2 \
  --min-tls-version TLS1_2 \
  --allow-blob-public-access false

# Create blob container for state
az storage container create \
  --name "$STATE_CONTAINER" \
  --account-name "$STATE_SA" \
  --auth-mode login
```

## 3. Configure the Project

Edit `targets/dev.yml` and replace the placeholder values:

```yaml
subscription_id: "YOUR_SUBSCRIPTION_ID"    # az account show --query id -o tsv
tenant_id: "YOUR_TENANT_ID"                # az account show --query tenantId -o tsv
```

Optionally adjust other parameters such as `location`, `vm_size`, `k8s_vm_size`, CIDR ranges, or database settings to fit your requirements.

## 4. Generate with geni

From the `azure_project/` directory:

```bash
cd quickstart/azure_project
geni -t dev
```

This generates the target and produces output in `generated/dev/`:

```
generated/dev/
  terraform/
    backend.tf
    provider.tf
    networking.tf.json
    iam.tf.json
    storage.tf.json
    compute.tf.json
    database.tf.json
    kubernetes.tf.json
    outputs.tf.json
  kubernetes/
    sample-app.yml
```

## 5. Deploy Infrastructure

```bash
cd generated/dev/terraform

# Initialize Terraform (downloads providers, configures backend)
terraform init

# Preview changes
terraform plan -out=tfplan

# Apply (review the plan output, then confirm)
terraform apply tfplan
```

The initial deployment takes approximately 15-25 minutes (AKS and PostgreSQL are the slowest resources).

## 6. Connect to AKS

Once Terraform finishes, configure kubectl:

```bash
az aks get-credentials \
  --resource-group rg-myazureproject-dev \
  --name aks-myazureproject-dev \
  --overwrite-existing

# Verify connectivity
kubectl get nodes
```

## 7. Deploy the Sample Application

Before deploying, update the workload identity client ID in the Kubernetes manifest. Get it from Terraform output:

```bash
# Get the app workload identity client ID
APP_CLIENT_ID=$(terraform -chdir=generated/dev/terraform output -raw identity_app_workload_client_id)

# Replace the placeholder in the manifest
sed -i "s/<APP_WORKLOAD_IDENTITY_CLIENT_ID>/$APP_CLIENT_ID/g" generated/dev/kubernetes/sample-app.yml
```

Deploy the application:

```bash
kubectl apply -f generated/dev/kubernetes/sample-app.yml

# Verify
kubectl -n sample-app get pods
kubectl -n sample-app get svc
```

## 8. SSH to the VM

Save the SSH private key and connect:

```bash
# Extract the SSH key
terraform -chdir=generated/dev/terraform output -raw vm_ssh_private_key > ~/.ssh/vm-myazureproject-dev.pem
chmod 600 ~/.ssh/vm-myazureproject-dev.pem

# Get the VM public IP
VM_IP=$(terraform -chdir=generated/dev/terraform output -raw vm_public_ip)

# Connect
ssh -i ~/.ssh/vm-myazureproject-dev.pem azureadmin@$VM_IP
```

## 9. Connect to PostgreSQL

The PostgreSQL server is on a private subnet and not directly accessible from the internet. Use the bastion VM as a jump host:

```bash
# Get connection details
DB_FQDN=$(terraform -chdir=generated/dev/terraform output -raw db_fqdn)
DB_PASS=$(terraform -chdir=generated/dev/terraform output -raw db_admin_password)

# SSH tunnel through the bastion VM
ssh -i ~/.ssh/vm-myazureproject-dev.pem \
  -L 5432:$DB_FQDN:5432 \
  azureadmin@$VM_IP -N &

# Connect via the tunnel
psql "host=localhost port=5432 dbname=appdb user=appuser password=$DB_PASS sslmode=require"
```

Alternatively, connect directly from the bastion VM:

```bash
ssh -i ~/.ssh/vm-myazureproject-dev.pem azureadmin@$VM_IP

# On the VM:
psql "host=psql-myazureproject-dev.postgres.database.azure.com port=5432 \
  dbname=appdb user=appuser password=<PASSWORD> sslmode=require"
```

## 10. Day 2 Operations

### Adding a new environment (e.g., staging)

1. Copy `targets/dev.yml` to `targets/staging.yml`
2. Update the metadata name, labels, and parameters (resource group, CIDRs, SKUs, etc.)
3. Compile: `geni -t staging`
4. Deploy: `cd generated/staging/terraform && terraform init && terraform apply`

### Scaling the AKS cluster

Edit `targets/dev.yml` and adjust:

```yaml
k8s_min_count: 2
k8s_max_count: 10
k8s_vm_size: Standard_D4s_v3
```

Regenerate and apply:

```bash
geni -t dev
cd generated/dev/terraform
terraform plan -out=tfplan
terraform apply tfplan
```

### Upgrading PostgreSQL

Update the `db_sku` parameter for a larger SKU:

```yaml
db_sku: GP_Standard_D2s_v3
db_storage_mb: 65536
```

### Adding new storage containers

Add entries to the `containers` list:

```yaml
containers:
  - app-data
  - app-logs
  - app-backups
```

## 11. Cleanup

### Destroy infrastructure

```bash
cd generated/dev/terraform
terraform destroy
```

Type `yes` when prompted.

### Delete the Terraform state backend

After all environments are destroyed:

```bash
az group delete --name rg-myazureproject-tfstate --yes --no-wait
```

## 12. Troubleshooting

### Terraform init fails with storage account error

Ensure the state storage account exists and you have the **Storage Blob Data Contributor** role:

```bash
az role assignment create \
  --role "Storage Blob Data Contributor" \
  --assignee $(az ad signed-in-user show --query id -o tsv) \
  --scope /subscriptions/$(az account show --query id -o tsv)/resourceGroups/rg-myazureproject-tfstate
```

### AKS nodes not ready

Check node status and events:

```bash
kubectl get nodes -o wide
kubectl describe node <node-name>
```

Verify the NAT gateway is associated with the AKS subnet for outbound connectivity.

### Cannot connect to PostgreSQL

- The database is on a private subnet. You must connect through the bastion VM or an SSH tunnel.
- Verify the private DNS zone link is active: `az network private-dns zone show --resource-group rg-myazureproject-dev --name myazureproject-dev.postgres.database.azure.com`
- Check NSG rules allow port 5432 from VNet sources.

### VM SSH connection refused

- Verify the NSG allows inbound SSH (port 22) from your IP.
- Check the VM is running: `az vm show --resource-group rg-myazureproject-dev --name vm-myazureproject-dev --show-details --query powerState`
- If you want to restrict SSH to your IP, update the bastion NSG `source_address_prefix` from `*` to your public IP.

### Workload identity not working

Verify the federated identity credential is configured:

```bash
az identity federated-credential list \
  --identity-name id-app-myazureproject-dev \
  --resource-group rg-myazureproject-dev
```

Ensure the ServiceAccount annotation matches the managed identity client ID and the pod has the `azure.workload.identity/use: "true"` label.

### Quota exceeded errors

Check your subscription quotas:

```bash
az vm list-usage --location eastus --output table
```

For dev environments, use smaller VM sizes (`Standard_B2s`, `B_Standard_B1ms`) to stay within free-tier or low-cost limits.
