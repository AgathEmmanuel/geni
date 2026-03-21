# Geni Architecture

Comprehensive architecture documentation for Geni, a Python-powered infrastructure-as-code generator.

---

## 1. System Overview

Geni takes declarative YAML target files and generates concrete infrastructure artifacts -- Terraform configurations, Kubernetes manifests, and Helm charts.

```mermaid
flowchart LR
    User["User / Developer"]
    YAML["Target YAML<br/>one per environment"]
    Generator["Geni Generator"]
    TF["Terraform<br/>.tf.json / .tf"]
    K8s["Kubernetes<br/>.yml manifests"]
    Helm["Helm Charts<br/>rendered"]

    User -->|writes| YAML
    YAML -->|input| Generator
    Generator -->|outputs| TF
    Generator -->|outputs| K8s
    Generator -->|outputs| Helm
```

The generator acts as a single translation layer between human-authored declarations and tool-specific output formats. One YAML file per environment drives all infrastructure generation consistently.

---

## 2. Core Architecture

```mermaid
graph TB
    subgraph Entry
        CLI["CLI<br/>cli.py<br/>Click-based entry point"]
    end

    subgraph Core
        Generator["Generator<br/>generator.py<br/>GeniGenerator orchestrator"]
        Schema["Schema<br/>schema.py<br/>Pydantic v2 validation"]
        Engine["Template Engine<br/>engine.py<br/>Loads and executes templates"]
        Templates["Template Base<br/>template.py<br/>GeneratedFile types + RenderContext"]
        Writers["Writers<br/>writers.py<br/>File serialization"]
        State["State<br/>state.py<br/>Lock file + atomic generation"]
    end

    subgraph Integrations
        HelmInt["Helm<br/>helm.py<br/>Chart resolution + rendering"]
        HCL["HCL<br/>hcl.py<br/>hcl2json conversion"]
    end

    subgraph Config
        GeniConfig["Config<br/>config.py<br/>.geni.yml loading"]
    end

    CLI --> Generator
    CLI --> GeniConfig
    Generator --> Schema
    Generator --> Engine
    Generator --> Writers
    Generator --> State
    Generator --> HelmInt
    Generator --> HCL
    Engine --> Templates
    Templates -->|render_helm| HelmInt
```

| Module | File | Responsibility |
|-----------|------|---------------|
| **CLI** | `cli.py` | Parses commands and flags, dispatches to the generator |
| **Generator** | `generator.py` | Central orchestrator -- validation, rendering, output |
| **Schema** | `schema.py` | Pydantic models for target YAML validation |
| **Engine** | `engine.py` | Discovers, loads, and executes templates |
| **Templates** | `template.py` | Base classes, GeneratedFile types, and RenderContext with built-in helpers |
| **Writers** | `writers.py` | Serializes GeneratedFile objects to disk |
| **State** | `state.py` | Lock files and atomic staging/swap |
| **Helm** | `integrations/helm.py` | Chart resolution (local + registry) and rendering |
| **HCL** | `integrations/hcl.py` | HCL-to-JSON conversion via hcl2json |
| **Config** | `config.py` | Project-level `.geni.yml` configuration |

---

## 3. Generation Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI as CLI
    participant Generator as Generator
    participant Schema as Schema
    participant Engine as TemplateEngine
    participant Helm as HelmIntegration
    participant Writers as FileWriter
    participant Atomic as AtomicGenerator
    participant Lock as LockFile

    User->>CLI: geni generate -t prod
    CLI->>Generator: generate_target(path)
    Generator->>Schema: parse YAML
    Schema->>Schema: Pydantic validate
    Schema-->>Generator: TargetManifest

    Generator->>Generator: resolve ${{ data.xxx }} refs
    Generator->>Lock: check input_hash
    Lock-->>Generator: unchanged? skip / proceed

    Generator->>Atomic: enter staging context

    loop Each Resource
        alt Template Resource
            Generator->>Engine: load_and_render(name, template, context)
            alt Python Template (.py)
                Engine->>Engine: importlib load module
                Engine->>Engine: find Template subclass
                Engine->>Engine: instance.render(context)
                Note over Engine: context.render_static() for HCL/JSON
                Note over Engine: context.render_helm() for Helm charts
            else Static Template (.tf/.yml/.json)
                Engine->>Engine: read file content
                Engine->>Engine: substitute ${{ var }}
                Engine->>Engine: parse to appropriate type
            end
            Engine-->>Generator: list[GeneratedFile]
            Generator->>Writers: write_all(files)
        else Chart Resource
            Generator->>Helm: render_helm_chart(chart, values)
            Helm-->>Generator: list of file paths
        end
    end

    Atomic->>Atomic: atomic swap staging -> output
    Generator->>Lock: update hashes
    Generator->>Lock: save .geni-lock.json
    Generator-->>CLI: list of written paths
    CLI-->>User: [+] Wrote N files
```

Key properties:

- **Validation-first**: target YAML is fully validated before any rendering begins
- **Reference resolution**: `${{ data.xxx }}` refs resolved after validation, before rendering
- **Atomic output**: files written to staging, swapped in one operation -- no partial writes

---

## 4. Template System

### Three Rendering Paths

```mermaid
flowchart TD
    Engine["TemplateEngine.load_and_render()"]
    Check{File extension?}

    subgraph Static ["Static Template Path"]
        Read["Read file content"]
        Sub["Substitute ${{ var }}"]
        Parse["Parse to dict or<br/>keep as text"]
        GF1["GeneratedFile"]
        Read --> Sub --> Parse --> GF1
    end

    subgraph Python ["Python Template Path"]
        Import["importlib load module"]
        Find["Find Template subclass<br/>or render() function"]
        Exec["Call render(context)"]
        GF2["GeneratedFile or list"]
        Import --> Find --> Exec --> GF2
    end

    subgraph HelmDirect ["Direct Helm Chart Path"]
        Resolve["Resolve chart<br/>(local or registry)"]
        HelmTemplate["helm template"]
        Files["Output files"]
        Resolve --> HelmTemplate --> Files
    end

    Engine --> Check
    Check -->|.tf .yml .json| Read
    Check -->|.py| Import
    Check -->|chart: in target| Resolve
```

### RenderContext Built-in Helpers

Python templates receive a `RenderContext` that provides helper methods for composing output from other sources:

```mermaid
flowchart LR
    subgraph RenderContext
        RS["render_static()"]
        RSJ["render_static_json()"]
        RH["render_helm()"]
        RHR["render_helm_registry()"]
    end

    HCL["Static .tf template"] --> RS --> Text["string"]
    JSON["Static .tf.json template"] --> RSJ --> Dict["dict"]
    LocalChart["Local Helm chart"] --> RH --> Manifests["list[dict]"]
    Registry["Registry Helm chart"] --> RHR --> Manifests2["list[dict]"]
```

| Method | Input | Returns | Use Case |
|--------|-------|---------|----------|
| `render_static(path, params)` | `.tf`, `.yml`, text template | `str` | Render HCL/text with substitution |
| `render_static_json(path, params)` | `.tf.json`, `.json` template | `dict` | Render JSON, get parsed dict |
| `render_helm(chart, ...)` | Local Helm chart path | `list[dict]` | Render chart, get parsed manifests |
| `render_helm_registry(repo, name, version, ...)` | Registry chart coordinates | `list[dict]` | Pull + render registry chart |

### Class Hierarchy

```mermaid
classDiagram
    class Template {
        +name: str
        +render(context: RenderContext) GeneratedFile
    }

    class RenderContext {
        +params: dict
        +data: dict
        +resources: dict
        +templates_dir: Path
        +output_dir: Path
        +render_static(path, params) str
        +render_static_json(path, params) dict
        +render_helm(chart, ...) list~dict~
        +render_helm_registry(repo, name, version, ...) list~dict~
    }

    class GeneratedFile {
        +filename: str
        +content: Any
        +file_type: str
    }

    class TerraformJSON {
        file_type = "tf.json"
        content: dict
    }

    class TerraformHCL {
        file_type = "tf"
        content: str
    }

    class KubernetesManifest {
        file_type = "yaml"
        content: dict | list
    }

    class RawFile {
        file_type = custom
        content: str
    }

    GeneratedFile <|-- TerraformJSON
    GeneratedFile <|-- TerraformHCL
    GeneratedFile <|-- KubernetesManifest
    GeneratedFile <|-- RawFile
    Template ..> RenderContext : receives
    Template ..> GeneratedFile : produces
```

**Static templates** are files with `${{ var }}` placeholders. Best for simple, mostly-literal configurations.

**Python templates** extend the `Template` base class with full Python logic -- loops, conditionals, API calls, multi-file output. They can call `render_static()` to reuse HCL/JSON templates or `render_helm()` to render and customize Helm charts programmatically.

**Direct Helm charts** are referenced via `chart:` in the target YAML and rendered as-is via `helm template`.

---

## 5. Target YAML Schema

```mermaid
classDiagram
    class TargetManifest {
        +apiVersion: "geni.io/v1alpha1"
        +kind: "Target"
        +metadata: Metadata
        +spec: Spec
    }

    class Metadata {
        +name: str
        +labels: dict~str,str~
    }

    class Spec {
        +data: dict~str,Any~
        +output: str
        +resources: dict~str,ResourceDef~
    }

    class ResourceDef {
        +template: str?
        +chart: ChartSource?
        +values: str?
        +params: dict~str,Any~
    }

    class ChartSource {
        +is_local: bool
    }

    class LocalChart {
        +path: str
    }

    class RegistryChart {
        +repo: str
        +name: str
        +version: str
    }

    TargetManifest --> Metadata
    TargetManifest --> Spec
    Spec --> ResourceDef
    ResourceDef --> ChartSource
    ChartSource <|-- LocalChart
    ChartSource <|-- RegistryChart
```

Each resource must specify exactly one of `template` or `chart`. The `params` dict is passed to the template at render time, with `${{ data.xxx }}` references resolved from the top-level `data` block.

---

## 6. State Management

### Atomic Generation

```mermaid
flowchart TD
    Start["Start generate"]
    Stage["Create .geni-staging-*/"]
    Write["Write all files to staging"]
    Check{Success?}
    Swap["Atomic rename<br/>staging -> output"]
    Restore["Restore .terraform/<br/>from backup"]
    Done["Generation complete"]
    Cleanup["Delete staging<br/>Keep original output"]
    Error["Report error"]

    Start --> Stage --> Write --> Check
    Check -->|Yes| Swap --> Restore --> Done
    Check -->|No| Cleanup --> Error
```

### Incremental Generation

```mermaid
flowchart LR
    Input["Target YAML"]
    Hash["Compute SHA256"]
    Compare{Hash matches<br/>lock file?}
    Skip["Skip generation"]
    Regenerate["Full regenerate"]
    Update["Update .geni-lock.json"]

    Input --> Hash --> Compare
    Compare -->|match| Skip
    Compare -->|mismatch or --force| Regenerate --> Update
```

Lock file structure (`.geni-lock.json`):

```json
{
  "version": 1,
  "generated_at": "2026-03-19T09:17:43+00:00",
  "targets": {
    "example-prod": {
      "input_hash": "sha256:abc123...",
      "outputs": {
        "backend.tf.json": "sha256:def456...",
        "provider.tf.json": "sha256:789abc..."
      }
    }
  }
}
```

The `.terraform/` directory is preserved across generations -- it is backed up before swap and restored after.

---

## 7. Plugin Architecture

```mermaid
flowchart TD
    subgraph Base
        TB["geni.template.Template<br/>base class"]
    end

    subgraph Builtins ["Built-in Templates"]
        TFB["geni.builtins.terraform<br/>Backend, Provider, Services<br/>Bucket, GKEAutopilot"]
        K8B["geni.builtins.kubernetes<br/>Namespace, Deployment"]
    end

    subgraph Local ["User Templates"]
        LT["templates/*.py<br/>Project-local Python templates"]
        LS["templates/*.tf / *.yml<br/>Static templates"]
        LC["charts/*<br/>Local Helm charts"]
    end

    subgraph Community ["Community Plugins"]
        EP["pip install geni-gcp-extras<br/>entry_points group: geni.generators"]
    end

    TB --> TFB
    TB --> K8B
    TB --> LT
    TB --> EP
```

Templates are discovered from three sources:

1. **Local templates** -- files in the project's `templates/` directory (referenced by relative path)
2. **Built-in templates** -- shipped with Geni in `geni.builtins`
3. **Community plugins** -- installed via pip, registered under `geni.generators` entry points

Helm charts can be local (in `charts/` directory) or pulled from registries.

---

## 8. User Workflows

### New Project

```mermaid
flowchart LR
    Init["geni init"] --> Edit["Edit targets/*.yml<br/>Add templates/"]
    Edit --> Validate["geni validate"]
    Validate --> Generate["geni generate"]
    Generate --> Verify["Review generated/"]
    Verify --> Apply["terraform apply<br/>kubectl apply"]
```

### Development Cycle

```mermaid
flowchart LR
    Change["Edit template<br/>or target YAML"] --> Diff["geni diff -t prod"]
    Diff --> Review{Changes OK?}
    Review -->|Yes| Generate["geni g -t prod"]
    Review -->|No| Change
    Generate --> Commit["git commit"]
```

### CI/CD Pipeline

```mermaid
flowchart LR
    Push["git push"] --> CI["CI Pipeline"]
    CI --> Lint["ruff check"]
    CI --> Test["pytest"]
    CI --> Generate["geni generate --all"]
    Generate --> Plan["terraform plan"]
    Plan --> Approve{PR Review}
    Approve -->|Merge| Apply["terraform apply"]
```

---

## 9. Design Patterns

| Pattern | Where | Purpose |
|---------|-------|---------|
| **Strategy** | `TemplateEngine._render_python_template` vs `_render_static_template` | Different rendering strategies based on file type |
| **Factory** | `TemplateEngine.load_and_render` | Discovers and instantiates Template subclasses dynamically |
| **Builder** | `GeneratedFile` subclasses (`TerraformJSON`, `KubernetesManifest`) | Construct output artifacts with type-specific defaults |
| **Context Manager** | `AtomicGenerator.__enter__/__exit__` | Safe staging/swap with automatic cleanup on failure |
| **Template Method** | `Template.render()` | Base class defines interface, subclasses implement logic |
| **Facade** | `GeniGenerator` | Single interface over engine, writers, state, and integrations |
| **Composition** | `RenderContext.render_static/render_helm` | Templates compose output from other templates and Helm charts |

```mermaid
flowchart TD
    subgraph Strategy ["Strategy Pattern"]
        TS["Template (interface)"]
        TJ["TerraformJSON"]
        TH["TerraformHCL"]
        KM["KubernetesManifest"]
        TS -.->|implements| TJ
        TS -.->|implements| TH
        TS -.->|implements| KM
    end

    subgraph Factory ["Factory Pattern"]
        TE["TemplateEngine"]
        TE -->|discovers + creates| TS
    end

    subgraph ContextMgr ["Context Manager"]
        AC["AtomicGenerator"]
    end

    subgraph Composition ["Composition via RenderContext"]
        RC["RenderContext"]
        RC -->|render_static| StaticTpl["Static templates"]
        RC -->|render_helm| HelmCharts["Helm charts"]
    end
```

---

## 10. Future: Agentic Architecture

An LLM agent sits between the user and Geni, translating natural language requirements into target YAML. The human retains full review authority before any generation or deployment occurs.

```mermaid
flowchart TD
    User["User<br/>natural language"]
    Agent["LLM Agent<br/>requirement translator"]
    Interview["Clarifying questions"]
    GenerateYAML["Generate / modify<br/>target YAML"]
    Review["Human Review<br/>diff in PR"]
    Approved{Approved?}
    Generate["geni generate"]
    Artifacts["Generated Artifacts"]
    GitOps["GitOps Pipeline<br/>ArgoCD / Flux"]
    Deploy["Infrastructure<br/>Deployed"]

    User --> Agent
    Agent --> Interview --> Agent
    Agent --> GenerateYAML --> Review
    Review --> Approved
    Approved -->|yes| Generate
    Approved -->|no| Agent
    Generate --> Artifacts --> GitOps --> Deploy
```

```mermaid
sequenceDiagram
    participant User
    participant Agent as LLM Agent
    participant Git as Git Repository
    participant Geni as Geni Generator
    participant GitOps as GitOps Controller

    User->>Agent: "Add a Redis cache to staging"
    Agent->>Git: Read existing target YAML
    Git-->>Agent: Current state
    Agent->>Agent: Generate updated target YAML
    Agent->>User: Propose diff for review
    User->>Agent: Approve
    Agent->>Git: Commit updated YAML
    Git->>Geni: CI triggers geni generate
    Geni->>Git: Commit generated artifacts
    Git->>GitOps: Sync detected
    GitOps-->>User: Redis cache running in staging
```

The agent's job is **requirements to YAML**. Geni's job is **YAML to infrastructure**. The YAML is the contract between them -- human-readable, git-tracked, reviewable. The agent never bypasses the generator or deploys directly.
