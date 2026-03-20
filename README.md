# geni

**Python-powered infrastructure-as-code compiler.**

One YAML per environment, compiled into Terraform, Kubernetes, and Helm artifacts.

<!-- [![PyPI version](https://badge.fury.io/py/geni.svg)](https://pypi.org/project/geni/) -->
<!-- [![CI](https://github.com/AgathEmmanuel/geni/actions/workflows/ci.yml/badge.svg)](https://github.com/AgathEmmanuel/geni/actions) -->
<!-- [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE) -->

---

## How It Works

```
targets/dev.yml          geni compile         compiled/dev/
targets/test.yml    ──────────────────►    compiled/test/
targets/prod.yml                           compiled/prod/
        │                                        │
        ▼                                        ▼
   One YAML per env                    Terraform .tf.json
   defines all infra                   Kubernetes .yml
                                       Helm charts
```

You write **one YAML target per environment**. Each target references **templates** (Python or static) that generate the actual infrastructure files. Change a parameter in the YAML, recompile, and all downstream artifacts update consistently.

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

Compile and inspect:

```bash
geni -t example
ls compiled/terraform/example/
```

### Option 2: Clone this repo and use the included targets

This repo ships with three ready-to-use GCP targets (dev, test, prod) demonstrating a full infrastructure stack:

```bash
git clone https://github.com/AgathEmmanuel/geni.git
cd geni
pip install .

# See what's available
ls targets/
# dev.yml  test.yml  prod.yml

# Compile the dev environment
geni -t dev

# Compile all environments
geni
```

After compilation, inspect the output:

```bash
ls compiled/dev/
# backend.tf          networking.tf.json    compute.tf.json
# provider.tf         iam.tf.json           kubernetes.tf.json
# storage.tf.json     00-namespace.yml      01-configmap.yml
# 02-serviceaccount.yml  03-deployment.yml  04-service.yml
```

---

## Working with Targets

### Understanding the included targets

The repo includes three environment targets for GCP, each producing Terraform + Kubernetes artifacts:

| Target | Environment | Machine Type | GKE Cluster | Buckets |
|--------|-------------|-------------|-------------|---------|
| `dev.yml` | dev | e2-medium | dev-cluster | app-assets, app-uploads |
| `test.yml` | test | e2-medium | test-cluster | app-assets, app-uploads, test-artifacts |
| `prod.yml` | prod | e2-standard-4 | prod-cluster | app-assets, app-uploads, app-backups |

Each target compiles into 12 files:
- **Terraform**: backend, provider, networking (VPC/subnets/firewall/NAT), IAM (service accounts), storage (GCS buckets), compute (bastion instance), kubernetes (GKE Autopilot)
- **Kubernetes**: namespace, configmap, serviceaccount, deployment, service

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

2. Compile:

```bash
geni -t dev
```

3. Deploy:

```bash
cd compiled/dev
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
  output: compiled/staging        # separate output dir
  resources:
    # same resources as dev, or add/remove as needed
```

Compile:

```bash
geni -t staging
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

3. Compile:

```bash
geni -t dev
# [+] Wrote 13 files for target 'dev'
```

### Removing a resource

Delete the resource block from the target YAML and recompile. The compiled output is fully regenerated each time.

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
  output: <string>          # output directory for compiled artifacts
  resources:
    <resource-name>:
      template: <path>      # path to template (relative to templates_dir)
      params:               # parameters passed to the template
        key: value
```

Each resource must specify exactly one source: `template`, `chart`, or `generator`.

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

## Common Workflows

### Validate before compiling

```bash
geni validate -t dev          # validate a single target
geni validate                 # validate all targets
```

### Preview changes without writing

```bash
geni -t dev --dry-run
# [+] Would write 12 files for target 'dev'
```

### See what changed

```bash
geni diff -t dev
```

### Force recompile (skip incremental cache)

```bash
geni -t dev --force
```

### Compile all environments at once

```bash
geni
# [+] Wrote 12 files for target 'dev'
# [+] Wrote 12 files for target 'test'
# [+] Wrote 12 files for target 'prod'
```

### Deploy compiled output

```bash
# Terraform
cd compiled/dev
terraform init
terraform plan -out=tfplan
terraform apply tfplan

# Kubernetes (after cluster is up)
kubectl apply -f compiled/dev/00-namespace.yml
kubectl apply -f compiled/dev/01-configmap.yml
kubectl apply -f compiled/dev/02-serviceaccount.yml
kubectl apply -f compiled/dev/03-deployment.yml
kubectl apply -f compiled/dev/04-service.yml
```

---

## Incremental Compilation

geni tracks state in `.geni-lock.json` inside each target's output directory. On subsequent runs, if the target YAML hasn't changed, compilation is skipped:

```
INFO Target 'dev' is up to date; skipping. Use --force to recompile.
```

Use `--force` to bypass the cache:

```bash
geni -t dev --force
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

When invoked without a subcommand, geni compiles directly: `geni -t dev` is equivalent to `geni compile -t dev`.

**Global options:**

| Flag | Description |
|------|-------------|
| `--version` | Show version and exit |
| `-v, --verbose` | Increase verbosity (`-v` info, `-vv` debug) |
| `-t, --target` | Target name to compile (without `.yml`) |
| `--dry-run` | Show what would be compiled without writing |
| `--force` | Force recompilation even if unchanged |

**Commands:**

| Command | Description |
|---------|-------------|
| `geni compile` | Compile targets (also the default action) |
| `geni validate` | Validate target YAML against the schema |
| `geni diff` | Show what would change if recompiled |
| `geni init` | Scaffold a new geni project |
| `geni migrate` | Migrate legacy format targets to v1alpha1 |

---

## Helm Integration

geni can render Helm charts as part of compilation:

```yaml
resources:
  # Local chart
  prometheus:
    chart:
      path: charts/prometheus
    values: values/prometheus-values.yml
    params:
      retention: 30d

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

---

## Configuration

Project configuration lives in `.geni.yml` at the project root:

```yaml
templates_dir: templates       # where templates live
targets_dir: targets           # where target YAMLs live
compiled_dir: compiled         # base output directory
```

All paths are relative to the project root. Defaults are used if `.geni.yml` doesn't exist.

---

## Project Structure

```
geni/
├── src/geni/                  # core package
│   ├── cli.py                 # Click CLI entry point
│   ├── compiler.py            # compilation orchestrator
│   ├── engine.py              # template loading and rendering
│   ├── schema.py              # Pydantic v2 target validation
│   ├── template.py            # Template base class + GeneratedFile types
│   ├── writers.py             # file serialization
│   ├── state.py               # lock file + atomic compilation
│   ├── config.py              # .geni.yml loader
│   ├── compat.py              # legacy format migration
│   ├── builtins/              # built-in template library
│   └── integrations/          # helm, hcl2json
├── templates/                 # project templates
│   ├── terraform/             # backend.tf, provider.tf, networking.py, ...
│   └── kubernetes/            # sample_app.py
├── targets/                   # environment targets
│   ├── dev.yml
│   ├── test.yml
│   └── prod.yml
├── tests/                     # test suite (59 tests)
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

See [ARCHITECTURE.md](ARCHITECTURE.md) for compilation pipeline details, module design, template system internals, and mermaid diagrams.

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
