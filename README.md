# geni

**Python-powered infrastructure-as-code compiler.**

One YAML per environment, compiled into Terraform, Kubernetes, and Helm artifacts.

<!-- Badges placeholder -->
<!-- [![PyPI version](https://badge.fury.io/py/geni.svg)](https://pypi.org/project/geni/) -->
<!-- [![CI](https://github.com/AgathEmmanuel/geni/actions/workflows/ci.yml/badge.svg)](https://github.com/AgathEmmanuel/geni/actions) -->
<!-- [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE) -->

---

## Features

- Single declarative YAML target per environment drives all IaC generation
- Versioned schema (`apiVersion: geni.io/v1alpha1`, `kind: Target`) with Pydantic validation
- Python templates for complex logic -- loops, conditionals, API calls, multi-file output
- Static templates with `${{ var }}` substitution for simple cases
- Legacy `__var__` placeholder syntax supported for backward compatibility
- Atomic compilation via staging directory swap (preserves `.terraform` state)
- Incremental compilation with lock file (`.geni-lock.json`) -- only recompile what changed
- Helm chart support for both local charts and remote registries
- HCL-to-JSON conversion via `hcl2json`
- Built-in template library for common Terraform and Kubernetes resources
- Plugin architecture via Python `entry_points`
- Click-based CLI: `compile`, `validate`, `diff`, `init`, `migrate`
- pip-installable with no system dependencies beyond Python 3.10+

---

## Quick Start

### Install

```bash
pip install geni
```

Or install from source:

```bash
git clone https://github.com/AgathEmmanuel/geni.git
cd geni
pip install .
```

### Initialize a project

```bash
geni init
```

This creates:

- `targets/example.yml` -- an example target file
- `templates/terraform/backend.tf` -- an example static template
- `.geni.yml` -- project configuration

### Compile

```bash
# Compile a specific target
geni -t example

# Compile all targets
geni

# Preview without writing files
geni -t example --dry-run

# Explicit compile subcommand also works
geni compile -t example
```

---

## Target YAML Format

Targets use the `geni.io/v1alpha1` schema. Each target file lives in the `targets/` directory and defines one environment's complete infrastructure.

### Schema

```yaml
apiVersion: geni.io/v1alpha1
kind: Target
metadata:
  name: <string>           # unique name for this target
  labels:                   # optional key-value labels
    environment: <string>
spec:
  data:                     # global variables available to all resources
    key: value
  output: <string>          # output directory for compiled artifacts
  resources:                # map of resource name -> resource definition
    <resource-name>:
      template: <path>      # path to template (relative to templates_dir)
      params:               # parameters passed to the template
        key: value
```

Each resource must specify exactly one source: `template`, `chart`, or `generator`.

### Complete Example

```yaml
apiVersion: geni.io/v1alpha1
kind: Target
metadata:
  name: production
  labels:
    environment: prod
    team: platform
spec:
  data:
    project: my-project
    region: us-central1
    cluster_name: prod-cluster
    namespace: production

  output: compiled/production

  resources:
    # --- Terraform resources (static template) ---
    backend:
      template: terraform/backend.tf
      params:
        bucket_name: my-project-tfstate
        tfstate_prefix: prod

    # --- Terraform resources (Python template) ---
    buckets:
      template: terraform/buckets.py
      params:
        buckets:
          - name: my-project-data
            location: US
          - name: my-project-logs
            location: US

    # --- Kubernetes resource ---
    namespace:
      template: kubernetes/namespace.yml
      params:
        namespace: ${{ data.namespace }}

    # --- Helm chart (local) ---
    prometheus:
      chart:
        path: charts/prometheus
      values: values/prometheus-values.yml
      params:
        retention: 30d
        storageSize: 50Gi

    # --- Helm chart (registry) ---
    cert-manager:
      chart:
        repo: https://charts.jetstack.io
        name: cert-manager
        version: 1.14.0
      params:
        installCRDs: true
```

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
        region: ${{ data.region }}
```

---

## Template Types

geni supports two types of templates: static templates and Python templates.

### Static Templates

Static templates are plain text files (`.tf`, `.yml`, `.json`, etc.) with placeholder substitution. Placeholders are replaced at compile time with values from `params` and `data`.

**New syntax** -- `${{ }}`:

```hcl
terraform {
  backend "gcs" {
    bucket = "${{ bucket_name }}"
    prefix = "${{ tfstate_prefix }}"
  }
}
```

**Legacy syntax** -- `__var__`:

```yaml
metadata:
  name: __project__-namespace
  namespace: __namespace__
```

Both syntaxes are processed during compilation. The `${{ }}` syntax is preferred for new templates.

### Python Templates

Python templates subclass `geni.template.Template` and implement a `render()` method. They receive a `RenderContext` containing `params`, `data`, references to previously compiled `resources`, and directory paths.

```python
from geni.template import Template, GeneratedFile, RenderContext

class MyTemplate(Template):
    def render(self, context: RenderContext) -> GeneratedFile | list[GeneratedFile]:
        # Build and return GeneratedFile instances
        ...
```

Available output types:

| Class                | File Type   | Content Type       |
|----------------------|-------------|--------------------|
| `TerraformJSON`      | `.tf.json`  | `dict`             |
| `TerraformHCL`       | `.tf`       | `str`              |
| `KubernetesManifest` | `.yml`      | `dict` or `list`   |
| `RawFile`            | any         | `str`              |

Alternatively, a Python template can define a module-level `render(context)` function instead of a class.

---

## Python Template Examples

### Simple Example -- Single File Output

A template that generates a Kubernetes Namespace manifest:

```python
# templates/kubernetes/namespace.py

from geni.template import Template, KubernetesManifest, GeneratedFile, RenderContext


class Namespace(Template):
    """Generates a Kubernetes Namespace manifest."""

    def render(self, context: RenderContext) -> GeneratedFile:
        manifest = {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": context.params["namespace"],
            },
            "spec": {},
        }

        labels = context.params.get("labels")
        if labels:
            manifest["metadata"]["labels"] = labels

        return KubernetesManifest(f"{self.name}.yml", manifest)
```

### Complex Example -- Multiple Files with Loops and Conditionals

A template that generates multiple GCS bucket resources with conditional configuration:

```python
# templates/terraform/buckets.py

from geni.template import Template, TerraformJSON, GeneratedFile, RenderContext


class MultiBucket(Template):
    """Generates Terraform resources for multiple GCS buckets.

    Params:
        buckets: list of dicts with 'name', 'location', 'versioning' (optional)
        lifecycle_days: int, optional days for lifecycle rule
        project: str
    """

    def render(self, context: RenderContext) -> list[GeneratedFile]:
        files = []
        project = context.params.get("project", context.data.get("project"))
        lifecycle_days = context.params.get("lifecycle_days")

        for bucket in context.params["buckets"]:
            name = bucket["name"]
            safe_name = name.replace("-", "_")

            resource_body = {
                "name": name,
                "location": bucket.get("location", "US"),
                "project": project,
                "uniform_bucket_level_access": True,
                "force_destroy": False,
            }

            # Conditional: add versioning only if requested
            if bucket.get("versioning", True):
                resource_body["versioning"] = [{"enabled": True}]

            # Conditional: add lifecycle rule if days specified
            if lifecycle_days:
                resource_body["lifecycle_rule"] = [{
                    "action": [{"type": "Delete"}],
                    "condition": [{"age": lifecycle_days}],
                }]

            tf_json = {
                "resource": [{
                    "google_storage_bucket": [{
                        safe_name: resource_body,
                    }]
                }]
            }

            files.append(TerraformJSON(f"{safe_name}.tf.json", tf_json))

        return files
```

Target usage:

```yaml
resources:
  storage:
    template: terraform/buckets.py
    params:
      project: ${{ data.project }}
      lifecycle_days: 90
      buckets:
        - name: app-data-prod
          location: US
          versioning: true
        - name: app-logs-prod
          location: US
          versioning: false
```

This produces two files: `app_data_prod.tf.json` and `app_logs_prod.tf.json`.

---

## Built-in Templates

geni ships with a built-in template library under `geni.builtins`. These can be referenced directly or used as examples for custom templates.

### Terraform (`geni.builtins.terraform`)

| Template   | Description                          |
|------------|--------------------------------------|
| `backend`  | Terraform backend configuration      |
| `bucket`   | Google Cloud Storage bucket(s)       |
| `gke_autopilot` | GKE Autopilot cluster           |
| `provider` | Terraform provider configuration     |
| `services` | Google Cloud API service enablement  |

### Kubernetes (`geni.builtins.kubernetes`)

| Template    | Description                        |
|-------------|------------------------------------|
| `deployment`| Kubernetes Deployment manifest     |
| `namespace` | Kubernetes Namespace manifest      |

---

## CLI Reference

```
geni [OPTIONS] COMMAND [ARGS]
```

**Global options:**

| Flag             | Description                                   |
|------------------|-----------------------------------------------|
| `--version`      | Show version and exit                         |
| `-v, --verbose`  | Increase verbosity (`-v` info, `-vv` debug)   |
| `-t, --target`   | Target name to compile (without `.yml`)       |
| `--dry-run`      | Show what would be compiled without writing   |
| `--force`        | Force recompilation even if unchanged         |

When invoked without a subcommand, geni compiles directly: `geni -t prod` is equivalent to `geni compile -t prod`.

### geni compile

Compile target YAML into infrastructure artifacts.

```bash
geni compile [OPTIONS]
```

| Flag              | Description                                    |
|-------------------|------------------------------------------------|
| `-t, --target`    | Target name to compile (without `.yml`)        |
| `--all`           | Compile all targets in the targets directory   |
| `--dry-run`       | Show what would be compiled without writing    |
| `--force`         | Force recompilation even if unchanged          |

When no flag is specified, all targets are compiled by default.

### geni validate

Validate target YAML files against the schema.

```bash
geni validate [OPTIONS]
```

| Flag              | Description                                    |
|-------------------|------------------------------------------------|
| `-t, --target`    | Target name to validate                        |
| `--all`           | Validate all targets                           |

### geni diff

Show what would change if a target were recompiled.

```bash
geni diff -t <target>
```

| Flag              | Description                                    |
|-------------------|------------------------------------------------|
| `-t, --target`    | (Required) Target name to diff                 |

### geni init

Initialize a new geni project with example files.

```bash
geni init [OPTIONS]
```

| Flag              | Description                                    |
|-------------------|------------------------------------------------|
| `--dir`           | Directory to initialize (default: `.`)         |

### geni migrate

Migrate legacy format files to the current schema.

```bash
geni migrate [OPTIONS]
```

| Flag              | Description                                    |
|-------------------|------------------------------------------------|
| `--targets`       | Migrate target files to `v1alpha1` format      |

---

## Project Structure

```
geni/
├── src/
│   └── geni/
│       ├── __init__.py            # Package version
│       ├── cli.py                 # Click CLI entry point
│       ├── compiler.py            # Main compilation orchestrator
│       ├── config.py              # GeniConfig loader (.geni.yml)
│       ├── engine.py              # Template loading and rendering engine
│       ├── schema.py              # Pydantic models (TargetManifest, ResourceDef)
│       ├── template.py            # Base Template class and GeneratedFile types
│       ├── writers.py             # File output writers
│       ├── state.py               # Lock file and atomic compilation
│       ├── compat.py              # Legacy format detection and migration
│       ├── errors.py              # Custom exception hierarchy
│       ├── filters.py             # String sanitization utilities
│       ├── builtins/
│       │   ├── terraform/
│       │   │   ├── backend.py
│       │   │   ├── bucket.py
│       │   │   ├── gke_autopilot.py
│       │   │   ├── provider.py
│       │   │   └── services.py
│       │   └── kubernetes/
│       │       ├── deployment.py
│       │       └── namespace.py
│       └── integrations/
│           ├── helm.py            # Helm chart rendering
│           └── hcl.py             # HCL to JSON conversion
├── tests/
│   ├── conftest.py
│   ├── test_cli.py
│   ├── test_compat.py
│   ├── test_compiler.py
│   ├── test_engine.py
│   ├── test_schema.py
│   └── test_state.py
├── pyproject.toml
├── .geni.yml
└── README.md
```

---

## Configuration

Project configuration is stored in `.geni.yml` at the project root.

```yaml
templates_dir: templates       # directory containing template files
targets_dir: targets           # directory containing target YAML files
compiled_dir: compiled         # base directory for compiled output
```

All paths are relative to the project root. If `.geni.yml` does not exist, geni uses the defaults shown above.

---

## Helm Integration

geni can render Helm charts as part of the compilation pipeline, supporting both local charts and remote registries.

### Local Charts

Reference a chart by its filesystem path:

```yaml
resources:
  kube-state-metrics:
    chart:
      path: charts/kube-state-metrics
    values: values/kube-state-metrics-values.yml
    params:
      replicas: 2
```

### Registry Charts

Pull a chart from a Helm repository:

```yaml
resources:
  cert-manager:
    chart:
      repo: https://charts.jetstack.io
      name: cert-manager
      version: 1.14.0
    params:
      installCRDs: true
```

### Values Files

Values files support the same `${{ }}` substitution as other templates. Parameters specified in `params` are merged into the rendered values, with `params` taking precedence.

---

## Incremental Compilation

geni tracks compilation state in a `.geni-lock.json` file stored in each target's output directory. The lock file records:

- The SHA256 hash of the target YAML input
- The SHA256 hash of each generated output file
- A timestamp of the last successful compilation

On subsequent runs, geni compares the current input hash against the lock file. If unchanged, compilation is skipped:

```
INFO Target 'production' is up to date (hash a3f8c1d2b9e4...); skipping. Use --force to recompile.
```

To force recompilation regardless of state:

```bash
geni compile -t production --force
```

The lock file format:

```json
{
  "version": 1,
  "compiled_at": "2026-03-19T10:30:00+00:00",
  "targets": {
    "production": {
      "input_hash": "a3f8c1d2b9e4...",
      "outputs": {
        "backend.tf.json": "sha256...",
        "buckets.tf.json": "sha256..."
      }
    }
  }
}
```

---

## Legacy Format Migration

geni supports the legacy target format for backward compatibility. Legacy targets lack an `apiVersion` field and use older key names:

| Legacy Key     | Current Key    |
|----------------|----------------|
| `compiled`     | `spec.output`  |
| `data`         | `spec.data`    |
| `parameter`    | `params`       |
| `component`    | `template`     |
| `value`        | `values`       |

Legacy targets are automatically detected and upgraded in memory at compile time. To permanently migrate files on disk:

```bash
geni migrate --targets
```

This rewrites each legacy target file in place, converting it to the `geni.io/v1alpha1` format.

Legacy `__var__` placeholder syntax in templates continues to work alongside the new `${{ var }}` syntax. No migration is required for template files.

---

## Development

### Install for development

```bash
git clone https://github.com/AgathEmmanuel/geni.git
cd geni
pip install -e ".[dev]"
```

### Run tests

```bash
pytest
```

Tests requiring external tools (Helm, hcl2json) are marked with `@pytest.mark.integration` and can be excluded:

```bash
pytest -m "not integration"
```

### Linting

```bash
ruff check src/ tests/
```

### Type checking

```bash
mypy src/geni/
```

---

## Architecture

For a detailed overview of the compilation pipeline, module responsibilities, and extension points, see [ARCHITECTURE.md](ARCHITECTURE.md).

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
