# GCP Quickstart: Full Infrastructure with geni

This quickstart deploys a complete GCP development environment using geni to compile YAML targets into Terraform and Kubernetes artifacts. The infrastructure includes:

- **Networking**: VPC, subnets with GKE secondary ranges, firewall rules, Cloud NAT
- **IAM**: Service accounts with least-privilege bindings, Workload Identity
- **Storage**: Multiple GCS buckets with lifecycle policies
- **Compute**: Bastion host (GCE) with SSH access and tooling
- **Database**: Cloud SQL PostgreSQL 15 with private networking
- **Kubernetes**: GKE Autopilot cluster
- **Sample App**: Kubernetes Deployment, Service, ConfigMap, and ServiceAccount

## 1. Prerequisites

Before starting, ensure you have the following installed:

```bash
# Google Cloud SDK
gcloud version
# Expected: Google Cloud SDK 450.0.0 or later

# Terraform
terraform version
# Expected: Terraform v1.5.0 or later

# kubectl
kubectl version --client
# Expected: v1.28.0 or later

# geni
geni --version
```

You also need:
- A GCP project with billing enabled
- Owner or Editor role on the project
- The following APIs will be enabled in step 3

## 2. Install geni

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

## 3. Initial GCP Setup

### Authenticate with GCP

```bash
# Login to GCP
gcloud auth login

# Set your project
export PROJECT_ID="my-gcp-project"
gcloud config set project $PROJECT_ID

# Authenticate application default credentials (used by Terraform)
gcloud auth application-default login
```

### Enable Required APIs

```bash
gcloud services enable \
    compute.googleapis.com \
    container.googleapis.com \
    sqladmin.googleapis.com \
    servicenetworking.googleapis.com \
    iam.googleapis.com \
    storage.googleapis.com \
    cloudresourcemanager.googleapis.com \
    --project=$PROJECT_ID
```

### Create the Terraform State Bucket

The GCS bucket for storing Terraform state must be created manually before running Terraform:

```bash
gsutil mb -p $PROJECT_ID -l us-central1 -b on gs://${PROJECT_ID}-tfstate

# Enable versioning on the state bucket
gsutil versioning set on gs://${PROJECT_ID}-tfstate
```

## 4. Configure the Project

Navigate to the quickstart directory and update the target with your project ID:

```bash
cd quickstart/gcp_project
```

Edit `targets/dev.yml` and replace `my-gcp-project` with your actual GCP project ID in the `spec.data.project` field:

```yaml
spec:
  data:
    project: YOUR_PROJECT_ID    # <-- Change this
    region: us-central1
    ...
```

Also update the tfstate bucket name in the `backend` resource params:

```yaml
  resources:
    backend:
      template: terraform/backend.tf
      params:
        bucket_name: YOUR_PROJECT_ID-tfstate    # <-- Change this
        tfstate_prefix: dev
```

## 5. Compile with geni

From the `gcp_project/` directory, run geni to compile the dev target:

```bash
geni compile -t dev
```

This reads `targets/dev.yml`, processes all referenced templates, and writes the compiled output to `compiled/dev/`. After compilation, you will see:

```
compiled/dev/
├── terraform/
│   ├── backend.tf          # GCS backend configuration
│   ├── provider.tf         # Google provider configuration
│   ├── networking.tf.json  # VPC, subnets, firewall, NAT
│   ├── iam.tf.json         # Service accounts, IAM bindings
│   ├── storage.tf.json     # GCS buckets
│   ├── compute.tf.json     # Bastion GCE instance
│   ├── database.tf.json    # Cloud SQL PostgreSQL
│   ├── kubernetes.tf.json  # GKE Autopilot cluster
│   └── outputs.tf.json     # Terraform outputs
└── kubernetes/
    ├── 00-namespace.yml
    ├── 01-configmap.yml
    ├── 02-serviceaccount.yml
    ├── 03-deployment.yml
    └── 04-service.yml
```

You can inspect the compiled Terraform JSON to verify correctness:

```bash
cat compiled/dev/terraform/networking.tf.json | jq .
```

## 6. Deploy Infrastructure

### Initialize Terraform

```bash
cd compiled/dev/terraform

terraform init
```

You should see output confirming the GCS backend is configured and providers are installed.

### Plan the Deployment

Review what Terraform will create:

```bash
terraform plan -out=tfplan
```

This will show approximately 20+ resources to be created. Review the plan carefully, paying attention to:
- Network CIDR ranges
- Cloud SQL instance tier and configuration
- GKE cluster settings
- IAM bindings

### Apply

Deploy the infrastructure:

```bash
terraform apply tfplan
```

This will take approximately 15-25 minutes. The longest resources to provision are:
- GKE Autopilot cluster (~10-15 minutes)
- Cloud SQL instance (~5-10 minutes)
- Service Networking Connection (~3-5 minutes)

### Verify Outputs

After successful apply, view the outputs:

```bash
terraform output
```

To see sensitive outputs:

```bash
terraform output -json | jq .
```

## 7. Connect to GKE

Configure kubectl to connect to the new cluster:

```bash
gcloud container clusters get-credentials dev-cluster \
    --region us-central1 \
    --project $PROJECT_ID
```

Verify connectivity:

```bash
kubectl cluster-info
kubectl get namespaces
```

## 8. Deploy the Sample App

Apply the compiled Kubernetes manifests:

```bash
cd ../../../compiled/dev/kubernetes

# Apply all manifests in order
kubectl apply -f 00-namespace.yml
kubectl apply -f 01-configmap.yml
kubectl apply -f 02-serviceaccount.yml
kubectl apply -f 03-deployment.yml
kubectl apply -f 04-service.yml
```

Or apply all at once:

```bash
kubectl apply -f .
```

Verify the deployment:

```bash
# Check pods are running
kubectl get pods -n sample-app

# Check service
kubectl get svc -n sample-app

# Check deployment status
kubectl rollout status deployment/sample-app -n sample-app

# View configmap
kubectl describe configmap sample-app-config -n sample-app

# View service account annotations (Workload Identity)
kubectl describe serviceaccount sample-app -n sample-app
```

Port-forward to test the application locally:

```bash
kubectl port-forward -n sample-app svc/sample-app 8080:80
```

Open http://localhost:8080 in your browser to see the nginx welcome page.

## 9. Connect to Compute Instance

SSH into the bastion host using gcloud:

```bash
gcloud compute ssh dev-bastion \
    --zone us-central1-a \
    --project $PROJECT_ID
```

Once connected, verify the startup script installed the tools:

```bash
kubectl version --client
cloud-sql-proxy --version
```

## 10. Connect to Cloud SQL

### From the Bastion Host

First, get the database connection name:

```bash
# From your local machine
terraform -chdir=compiled/dev/terraform output database_connection_name
```

Then on the bastion host:

```bash
# Start cloud-sql-proxy (run in background or a separate terminal)
cloud-sql-proxy $PROJECT_ID:us-central1:dev-db --port=5432 &

# Connect with psql (install if needed: apt-get install -y postgresql-client)
PGPASSWORD=$(terraform -chdir=compiled/dev/terraform output -raw database_password) \
    psql -h 127.0.0.1 -U appuser -d appdb
```

### From GKE Pods

Applications running in GKE should use the Cloud SQL Proxy as a sidecar container. The ConfigMap already provides `DB_HOST=127.0.0.1` and `DB_PORT=5432` for this pattern.

## 11. Day 2 Operations

### Modifying Configuration

To change infrastructure parameters, edit `targets/dev.yml`. For example, to change the machine type:

```yaml
spec:
  data:
    machine_type: e2-standard-4    # Was e2-medium
```

Then recompile and apply:

```bash
cd quickstart/gcp_project
geni compile -t dev

cd compiled/dev/terraform
terraform plan -out=tfplan
terraform apply tfplan
```

### Adding a New Resource

To add a new resource, create a template and reference it from the target. For example, to add a Redis (Memorystore) instance:

1. Create `templates/terraform/redis.py`:

```python
from geni.template import Template, TerraformJSON, RenderContext

class RedisTemplate(Template):
    def render(self, context):
        params = context.params
        return TerraformJSON(name="redis", content={
            "resource": {
                "google_redis_instance": {
                    params["name"]: {
                        "name": params["name"],
                        "tier": "BASIC",
                        "memory_size_gb": 1,
                        "region": params["region"],
                        "authorized_network": f"${{google_compute_network.{params['network']}.id}}",
                    }
                }
            }
        })
```

2. Add it to `targets/dev.yml`:

```yaml
    redis:
      template: terraform/redis.py
      params:
        name: dev-redis
        region: ${{ data.region }}
        network: ${{ data.network_name }}
```

3. Recompile and apply:

```bash
geni compile -t dev
cd compiled/dev/terraform
terraform plan -out=tfplan
terraform apply tfplan
```

### Creating a New Environment

To create a staging or production environment, copy `targets/dev.yml` to a new file:

```bash
cp targets/dev.yml targets/staging.yml
```

Edit `targets/staging.yml` and update the values (project, environment label, resource names, machine types, etc.). Then compile the new target:

```bash
geni compile -t staging
```

The compiled output will be written to `compiled/staging/`.

## 12. Cleanup

### Destroy Infrastructure

Remove all GCP resources created by Terraform:

```bash
cd compiled/dev/terraform

# First remove Kubernetes resources
kubectl delete -f ../kubernetes/ --ignore-not-found

# Destroy Terraform-managed resources
terraform destroy
```

Type `yes` when prompted. Destruction takes approximately 10-15 minutes.

### Delete the Terraform State Bucket

After all resources are destroyed:

```bash
# Remove all objects (including versions)
gsutil -m rm -r gs://${PROJECT_ID}-tfstate/**

# Delete the bucket
gsutil rb gs://${PROJECT_ID}-tfstate
```

### Clean Up Compiled Artifacts

```bash
rm -rf compiled/
```

## 13. Troubleshooting

### API Not Enabled

```
Error: googleapi: Error 403: ... has not been used in project ... before or it is disabled.
```

**Fix**: Enable the required API:

```bash
gcloud services enable SERVICE_NAME.googleapis.com --project=$PROJECT_ID
```

### Insufficient Permissions

```
Error: googleapi: Error 403: Required '...' permission for '...'
```

**Fix**: Ensure your account has the Owner or Editor role, or grant the specific role:

```bash
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="user:YOUR_EMAIL" \
    --role="roles/editor"
```

### Service Networking Connection Timeout

The `google_service_networking_connection` resource can take several minutes. If it times out:

```bash
terraform apply -target=google_service_networking_connection.dev-sql-vpc-connection
terraform apply
```

### GKE Cluster Creation Fails

If the GKE cluster fails to create due to quota issues:

```bash
# Check your quotas
gcloud compute project-info describe --project=$PROJECT_ID | grep -A 2 CPUS

# Request a quota increase if needed
# Visit: https://console.cloud.google.com/iam-admin/quotas
```

### Cloud SQL Private IP Not Reachable

If you cannot connect to Cloud SQL from GKE or the bastion:

```bash
# Verify the private services connection exists
gcloud services vpc-peerings list --network=dev-network --project=$PROJECT_ID

# Verify the SQL instance has a private IP
gcloud sql instances describe dev-db --project=$PROJECT_ID --format="value(ipAddresses)"
```

### Terraform State Lock

If a previous Terraform run was interrupted:

```bash
terraform force-unlock LOCK_ID
```

### geni Compilation Errors

If `geni compile` fails:

```bash
# Validate the target YAML
geni validate -t dev

# Run with verbose output
geni compile -t dev --verbose
```

Common issues:
- **Template not found**: Verify `templates_dir` in `.geni.yml` matches your directory structure
- **Invalid reference**: Check that `${{ data.xxx }}` references match keys in `spec.data`
- **Python syntax error**: Check the template file for syntax issues
