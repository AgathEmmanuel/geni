# geni

**Python-powered infrastructure-as-code generator.**

One YAML per environment, generated into Terraform, Kubernetes, and Helm artifacts.

<!-- [![PyPI version](https://badge.fury.io/py/geni.svg)](https://pypi.org/project/geni/) -->
<!-- [![CI](https://github.com/AgathEmmanuel/geni/actions/workflows/ci.yml/badge.svg)](https://github.com/AgathEmmanuel/geni/actions) -->
<!-- [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE) -->

---

## How It Works

```
targets/dev.yml          geni generate        generated/dev/
targets/test.yml    ──────────────────►    generated/test/
targets/prod.yml                           generated/prod/
        │                                        │
        ▼                                        ▼
   One YAML per env                    Terraform .tf.json / .tf
   defines all infra                   Kubernetes .yml
                                       Helm charts (rendered)
```

You write **one YAML target per environment**. Each target references **templates** (Python or static) and **Helm charts** that generate the actual infrastructure files. Change a parameter in the YAML, regenerate, and all downstream artifacts update consistently.

---

## Install

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
python3 -m venv .venv
source .venv/bin/activate
pip install .
geni --version

# Or run directly without installing:
PYTHONPATH=src python3 -m geni --version
```

Install a specific version:

```bash
GENI_VERSION=0.1.0 curl -fsSL https://raw.githubusercontent.com/AgathEmmanuel/geni/main/install.sh | sh
```

---

## Quick Start

### Option 1: Bootstrap a new project

```bash
mkdir my-infra && cd my-infra
geni init
```

This creates a starter project:

```
my-infra/
├── .geni.yml                  # project config
├── targets/
│   └── example.yml            # example target
└── templates/
    └── terraform/
        └── backend.tf         # example static template
```

Generate and inspect:

```bash
geni generate -t example
ls generated/terraform/example/
```

### Option 2: Clone this repo and use the included targets

This repo ships with three ready-to-use GCP targets (dev, test, prod) demonstrating a full infrastructure stack with Terraform, Kubernetes, and Helm:

```bash
git clone https://github.com/AgathEmmanuel/geni.git
cd geni
pip install .

# See what's available
ls targets/
# dev.yml  test.yml  prod.yml

# Generate the dev environment
geni generate -t dev

# Generate all environments
geni generate
```

After generation, inspect the output:

```bash
ls generated/dev/
# backend.tf               provider.tf              redis.tf
# networking.tf.json       iam.tf.json              compute.tf.json
# storage.tf.json          kubernetes.tf.json
# 00-namespace.yml         01-configmap.yml         02-serviceaccount.yml
# 03-deployment.yml        04-service.yml
# monitoring-namespace-monitoring.yml
# monitoring-deployment-dev-monitoring-prometheus.yml
# monitoring-deployment-dev-monitoring-grafana.yml
# monitoring-service-dev-monitoring-prometheus.yml
# monitoring-service-dev-monitoring-grafana.yml
# nginx-ingress/templates/deployment.yaml
# nginx-ingress/templates/service.yaml
```

---

## Working with Targets

### Understanding the included targets

The repo includes three environment targets for GCP, each producing Terraform + Kubernetes + Helm artifacts:

| Target | Environment | Machine Type | GKE Cluster | Redis | Monitoring | Ingress |
|--------|-------------|-------------|-------------|-------|------------|---------|
| `dev.yml` | dev | e2-medium | dev-cluster | 1 instance (BASIC) | Prometheus + Grafana | 1 replica |
| `test.yml` | test | e2-medium | test-cluster | 2 instances (BASIC) | Prometheus + Grafana | 2 replicas |
| `prod.yml` | prod | e2-standard-4 | prod-cluster | 2 instances (STANDARD_HA) | Prometheus + Grafana (HA) | 3 replicas (LoadBalancer) |

Each target generates ~20 files across three categories:
- **Terraform**: backend, provider, networking (VPC/subnets/firewall/NAT), IAM (service accounts), storage (GCS buckets), compute (bastion instance), kubernetes (GKE Autopilot), redis (Memorystore)
- **Kubernetes**: namespace, configmap, serviceaccount, deployment, service
- **Helm**: nginx-ingress (direct chart), monitoring-stack (Python-customized chart with Prometheus + Grafana)

### Customizing a target for your project

1. Edit `targets/dev.yml` and update `spec.data` with your values:

```yaml
spec:
  data:
    project: your-gcp-project-id    # <-- your GCP project
    region: us-central1
    environment: dev
    cluster_name: dev-cluster
    machine_type: e2-medium
    app_name: my-service            # <-- your service name
    app_image: gcr.io/your-project/my-service:latest
```

2. Generate:

```bash
geni generate -t dev
```

3. Deploy:

```bash
cd generated/dev
terraform init && terraform plan
terraform apply

# Then deploy K8s manifests
kubectl apply -f 00-namespace.yml -f 01-configmap.yml \
  -f 02-serviceaccount.yml -f 03-deployment.yml -f 04-service.yml
```

### Creating a new target

Copy an existing target and modify it:

```bash
cp targets/dev.yml targets/staging.yml
```

Edit `targets/staging.yml` -- update the name, labels, data values, and output path:

```yaml
apiVersion: geni.io/v1alpha1
kind: Target
metadata:
  name: staging
  labels:
    environment: staging
spec:
  data:
    project: my-gcp-project
    region: us-east1              # different region
    environment: staging
    cluster_name: staging-cluster
    machine_type: e2-standard-2   # bigger than dev
    # ... rest of data
  output: generated/staging        # separate output dir
  resources:
    # same resources as dev, or add/remove as needed
```

Generate:

```bash
geni generate -t staging
```

### Adding a new resource to a target

To add infrastructure, create a template and reference it from the target.

**Example: adding a Cloud SQL database**

1. Create `templates/terraform/database.py`:

```python
from geni.template import Template, TerraformJSON, RenderContext

class DatabaseTemplate(Template):
    def render(self, context):
        p = context.params
        return TerraformJSON("database.tf.json", {
            "resource": {
                "google_sql_database_instance": {
                    p["instance_name"]: {
                        "name": p["instance_name"],
                        "project": p["project"],
                        "region": p["region"],
                        "database_version": "POSTGRES_15",
                        "deletion_protection": False,
                        "settings": {
                            "tier": p.get("tier", "db-custom-2-7680"),
                        },
                    }
                },
                "google_sql_database": {
                    p["db_name"]: {
                        "name": p["db_name"],
                        "instance": f"${{google_sql_database_instance.{p['instance_name']}.name}}",
                    }
                },
            }
        })
```

2. Add it to `targets/dev.yml` under `resources`:

```yaml
    database:
      template: terraform/database.py
      params:
        project: ${{ data.project }}
        region: ${{ data.region }}
        instance_name: ${{ data.db_instance_name }}
        db_name: ${{ data.db_name }}
```

3. Generate:

```bash
geni generate -t dev
```

### Removing a resource

Delete the resource block from the target YAML and regenerate. The output is fully regenerated each time.

---

## Target YAML Format

### Schema

```yaml
apiVersion: geni.io/v1alpha1
kind: Target
metadata:
  name: <string>
  labels:
    environment: <string>
spec:
  data:                     # global variables available to all resources
    key: value
  output: <string>          # output directory for generated artifacts
  resources:
    <resource-name>:
      template: <path>      # path to template (relative to templates_dir)
      chart:                # OR a Helm chart source
        path: <local-path>  #   local chart
        # OR
        repo: <url>         #   registry chart
        name: <chart-name>
        version: <version>
      values: <path>        # optional values file for charts
      params:               # parameters passed to the template or chart
        key: value
```

Each resource must specify exactly one source: `template` or `chart`.

### Data References

Use `${{ data.xxx }}` in resource params to reference values from `spec.data`:

```yaml
spec:
  data:
    region: us-central1
  resources:
    provider:
      template: terraform/provider.tf
      params:
        region: ${{ data.region }}    # resolves to "us-central1"
```

---

## Template Types

### Static Templates

Plain text files (`.tf`, `.yml`, `.json`) with `${{ var }}` placeholder substitution:

```hcl
# templates/terraform/backend.tf
terraform {
  backend "gcs" {
    bucket = "${{ bucket_name }}"
    prefix = "${{ tfstate_prefix }}"
  }
}
```

### Python Templates

Python templates subclass `geni.template.Template` and implement `render()`. They receive a `RenderContext` with `params`, `data`, and directory paths, and return `GeneratedFile` instances.

```python
from geni.template import Template, TerraformJSON, KubernetesManifest, RenderContext

class MyTemplate(Template):
    def render(self, context: RenderContext) -> GeneratedFile | list[GeneratedFile]:
        # Full Python: loops, conditionals, API calls, multi-file output
        return TerraformJSON("output.tf.json", {"resource": {...}})
```

Available output types:

| Class | File Type | Content Type |
|---|---|---|
| `TerraformJSON` | `.tf.json` | `dict` |
| `TerraformHCL` | `.tf` | `str` |
| `KubernetesManifest` | `.yml` | `dict` or `list` |
| `RawFile` | any | `str` |

### Python Template Example -- Multiple Files

A template that generates one Terraform file per GCS bucket:

```python
# templates/terraform/storage.py
from geni.template import Template, TerraformJSON, RenderContext

class StorageTemplate(Template):
    def render(self, context):
        params = context.params
        bucket_resources = {}

        for bucket in params["buckets"]:
            name = f"{params['project']}-{params['environment']}-{bucket['name']}"
            resource_name = bucket["name"].replace("-", "_")
            bucket_resources[resource_name] = {
                "name": name,
                "project": params["project"],
                "location": params["region"],
                "uniform_bucket_level_access": True,
                "versioning": {"enabled": bucket.get("versioning", False)},
            }

        return TerraformJSON("storage.tf.json", {
            "resource": {"google_storage_bucket": bucket_resources}
        })
```

Target usage:

```yaml
storage:
  template: terraform/storage.py
  params:
    project: ${{ data.project }}
    region: ${{ data.region }}
    environment: ${{ data.environment }}
    buckets:
      - name: app-assets
        versioning: true
      - name: app-logs
        versioning: false
```

---

## render_static -- Reusing Static Templates from Python

Python templates can render static HCL/JSON templates with `${{ var }}` substitution using `context.render_static()`. This avoids converting large Terraform HCL to Python dicts -- write the HCL once as a static template, then loop over it from Python.

### render_static (HCL / text)

```python
# templates/terraform/redis.py
from geni.template import Template, TerraformHCL, RenderContext

class RedisTemplate(Template):
    def render(self, context):
        p = context.params
        blocks = []
        for instance in p["instances"]:
            hcl = context.render_static("terraform/redis.tf", {
                "resource_name": instance["name"].replace("-", "_"),
                "instance_name": f"{p['project']}-{p['environment']}-{instance['name']}",
                "project": p["project"],
                "region": p["region"],
                "tier": instance.get("tier", "BASIC"),
                "memory_size_gb": instance.get("memory_size_gb", 1),
            })
            blocks.append(hcl)
        return TerraformHCL("redis.tf", "\n".join(blocks))
```

Where `templates/terraform/redis.tf` is a standard HCL file with placeholders:

```hcl
resource "google_redis_instance" "${{ resource_name }}" {
  name           = "${{ instance_name }}"
  project        = "${{ project }}"
  region         = "${{ region }}"
  tier           = "${{ tier }}"
  memory_size_gb = ${{ memory_size_gb }}
}
```

### render_static_json (JSON / .tf.json)

For JSON-based templates, `render_static_json` returns a parsed `dict`:

```python
tf = context.render_static_json("terraform/bucket.tf.json", {
    "bucket_name": "my-bucket",
    "project": "my-project",
})
# tf is a dict -- merge, modify, combine as needed
```

---

## Helm Integration

### Direct chart resources

geni can render Helm charts directly as part of generation. Charts are rendered using `helm template` and output as-is:

```yaml
resources:
  # Local chart
  ingress:
    chart:
      path: charts/nginx-ingress
    params:
      namespace: my-app
      replicaCount: 2

  # Registry chart
  cert-manager:
    chart:
      repo: https://charts.jetstack.io
      name: cert-manager
      version: 1.14.0
    params:
      installCRDs: true
```

Values files support `${{ }}` substitution. `params` are merged into values with `params` taking precedence.

### Helm via Python templates (render_helm)

Python templates can render Helm charts and post-process the output -- inject labels, filter manifests, add annotations, or combine multiple charts:

```python
# templates/kubernetes/monitoring.py
from geni.template import Template, KubernetesManifest, RenderContext

class MonitoringTemplate(Template):
    def render(self, context):
        p = context.params

        # Render helm chart, get back list of parsed manifest dicts
        manifests = context.render_helm(
            chart=p["chart_path"],
            release_name=f"{p['environment']}-monitoring",
            values={"namespace": "monitoring", "prometheus": {"retention": p["retention"]}},
            namespace="monitoring",
        )

        results = []
        for m in manifests:
            kind = m.get("kind", "unknown")
            # Inject custom labels into every manifest
            m.setdefault("metadata", {}).setdefault("labels", {})["environment"] = p["environment"]

            # Add alert routing annotation to Deployments
            if kind == "Deployment" and p.get("alert_channel"):
                m["metadata"].setdefault("annotations", {})["alert-channel"] = p["alert_channel"]

            filename = f"monitoring-{kind.lower()}-{m['metadata'].get('name', 'unknown')}.yml"
            results.append(KubernetesManifest(filename, m))
        return results
```

For registry charts, use `render_helm_registry`:

```python
manifests = context.render_helm_registry(
    repo="https://charts.jetstack.io",
    name="cert-manager",
    version="1.14.0",
    values={"installCRDs": True},
)
```

| Approach | Target YAML | What you get |
|----------|-------------|--------------|
| **Direct `chart:`** | `chart: { path: charts/nginx }` | Black box -- helm output as-is |
| **Python + `render_helm()`** | `template: kubernetes/monitoring.py` | Full control -- filter, modify, combine manifests |

---

## Common Workflows

### Validate before generating

```bash
geni validate -t dev          # validate a single target
geni validate                 # validate all targets
```

### Preview changes without writing

```bash
geni -t dev --dry-run
```

### See what changed

```bash
geni diff -t dev
```

### Force regenerate (skip incremental cache)

```bash
geni generate -t dev --force
```

### Generate all environments at once

```bash
geni generate
# [+] Wrote 28 files for target 'dev'
# [+] Wrote 28 files for target 'test'
# [+] Wrote 28 files for target 'prod'
```

### Deploy generated output

```bash
# Terraform
cd generated/dev
terraform init
terraform plan -out=tfplan
terraform apply tfplan

# Kubernetes (after cluster is up)
kubectl apply -f generated/dev/00-namespace.yml
kubectl apply -f generated/dev/01-configmap.yml
kubectl apply -f generated/dev/02-serviceaccount.yml
kubectl apply -f generated/dev/03-deployment.yml
kubectl apply -f generated/dev/04-service.yml
```

---

## Incremental Generation

geni tracks state in `.geni-lock.json` inside each target's output directory. On subsequent runs, if the target YAML hasn't changed, generation is skipped:

```
INFO Target 'dev' is up to date; skipping. Use --force to regenerate.
```

Use `--force` to bypass the cache:

```bash
geni generate -t dev --force
```

---

## Cloud Quickstarts

The `quickstart/` directory contains complete, ready-to-deploy infrastructure projects for each major cloud:

| Directory | Cloud | What's Included |
|-----------|-------|-----------------|
| `quickstart/gcp_project/` | Google Cloud | VPC, GKE Autopilot, Cloud SQL, GCS, GCE, IAM |
| `quickstart/aws_project/` | AWS | VPC, EKS, RDS, S3, EC2, IAM/IRSA |
| `quickstart/azure_project/` | Azure | VNet, AKS, PostgreSQL Flexible, Storage, VM |

Each has its own `QUICKSTART.md` with step-by-step instructions from install to deploy to cleanup.

---

## CLI Reference

```
geni [OPTIONS] COMMAND [ARGS]
```

When invoked without a subcommand, geni generates directly: `geni -t dev` is equivalent to `geni generate -t dev`.

**Global options:**

| Flag | Description |
|------|-------------|
| `--version` | Show version and exit |
| `-v, --verbose` | Increase verbosity (`-v` info, `-vv` debug) |
| `-t, --target` | Target name to generate (without `.yml`) |
| `--dry-run` | Show what would be generated without writing |
| `--force` | Force regeneration even if unchanged |

**Commands:**

| Command | Alias | Description |
|---------|-------|-------------|
| `geni generate` | `geni g` | Generate targets (also the default action) |
| `geni validate` | | Validate target YAML against the schema |
| `geni diff` | | Show what would change if regenerated |
| `geni init` | | Scaffold a new geni project |

**Examples:**

```bash
geni generate -t dev       # generate a single target
geni g -t dev              # same thing, short alias
geni generate              # generate all targets
geni -t dev                # generate (default action, no subcommand needed)
geni g -t dev --force      # force regenerate
geni validate -t dev       # validate before generating
geni diff -t dev           # preview changes
```

---

## Configuration

Project configuration lives in `.geni.yml` at the project root:

```yaml
templates_dir: templates       # where templates live
targets_dir: targets           # where target YAMLs live
generated_dir: generated       # base output directory
```

All paths are relative to the project root. Defaults are used if `.geni.yml` doesn't exist.

---

## Project Structure

```
geni/
├── src/geni/                  # core package
│   ├── cli.py                 # Click CLI entry point
│   ├── generator.py           # generation orchestrator
│   ├── engine.py              # template loading and rendering
│   ├── schema.py              # Pydantic v2 target validation
│   ├── template.py            # Template base class, GeneratedFile types, RenderContext
│   ├── writers.py             # file serialization
│   ├── state.py               # lock file + atomic generation
│   ├── config.py              # .geni.yml loader
│   ├── errors.py              # error classes
│   ├── filters.py             # template filters
│   └── integrations/          # helm, hcl2json
├── templates/                 # project templates
│   ├── terraform/             # backend.tf, provider.tf, redis.tf (static)
│   │                          # networking.py, iam.py, storage.py, compute.py,
│   │                          # kubernetes.py, redis.py (Python)
│   └── kubernetes/            # sample_app.py, monitoring.py
├── charts/                    # Helm charts
│   ├── nginx-ingress/         # simple nginx ingress chart
│   └── monitoring-stack/      # Prometheus + Grafana chart
├── targets/                   # environment targets
│   ├── dev.yml
│   ├── test.yml
│   └── prod.yml
├── tests/                     # test suite (56 tests)
├── quickstart/                # cloud-specific quickstart projects
│   ├── gcp_project/
│   ├── aws_project/
│   └── azure_project/
├── pyproject.toml
├── install.sh
└── ARCHITECTURE.md
```

---

## Development

```bash
git clone https://github.com/AgathEmmanuel/geni.git
cd geni
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest

# Skip integration tests (require helm, hcl2json)
pytest -m "not integration"

# Lint
ruff check src/ tests/

# Type check
mypy src/geni/
```

---

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for generation pipeline details, module design, template system internals, and mermaid diagrams.

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add or update tests for your changes
4. Ensure `pytest`, `ruff check`, and `mypy` pass
5. Submit a pull request

---

## License

MIT -- see [LICENSE](LICENSE) for details.
