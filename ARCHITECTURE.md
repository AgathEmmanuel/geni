# Geni Architecture

Comprehensive architecture documentation for Geni, a Python-powered infrastructure-as-code compiler.

---

## 1. System Overview

Geni takes declarative YAML target files and compiles them into concrete infrastructure artifacts -- Terraform configurations, Kubernetes manifests, and Helm charts.

```mermaid
flowchart LR
    User["User / Developer"]
    YAML["Target YAML<br/>one per environment"]
    Compiler["Geni Compiler"]
    TF["Terraform<br/>.tf.json / .tf"]
    K8s["Kubernetes<br/>.yml manifests"]
    Helm["Helm Charts<br/>rendered"]

    User -->|writes| YAML
    YAML -->|input| Compiler
    Compiler -->|outputs| TF
    Compiler -->|outputs| K8s
    Compiler -->|outputs| Helm
```

The compiler acts as a single translation layer between human-authored declarations and tool-specific output formats. One YAML file per environment drives all infrastructure generation consistently.

---

## 2. Core Architecture

```mermaid
graph TB
    subgraph Entry
        CLI["CLI<br/>cli.py<br/>Click-based entry point"]
    end

    subgraph Core
        Compiler["Compiler<br/>compiler.py<br/>GeniCompiler orchestrator"]
        Schema["Schema<br/>schema.py<br/>Pydantic v2 validation"]
        Engine["Template Engine<br/>engine.py<br/>Loads and executes templates"]
        Templates["Template Base<br/>template.py<br/>GeneratedFile types"]
        Writers["Writers<br/>writers.py<br/>File serialization"]
        State["State<br/>state.py<br/>Lock file + atomic compilation"]
    end

    subgraph Integrations
        HelmInt["Helm<br/>helm.py<br/>Chart resolution + rendering"]
        HCL["HCL<br/>hcl.py<br/>hcl2json conversion"]
    end

    subgraph Migration
        Compat["Compat<br/>compat.py<br/>Legacy format migration"]
    end

    subgraph Config
        GeniConfig["Config<br/>config.py<br/>.geni.yml loading"]
    end

    CLI --> Compiler
    CLI --> GeniConfig
    Compiler --> Schema
    Compiler --> Engine
    Compiler --> Writers
    Compiler --> State
    Compiler --> HelmInt
    Compiler --> HCL
    Compiler --> Compat
    Engine --> Templates
```

| Component | File | Responsibility |
|-----------|------|---------------|
| **CLI** | `cli.py` | Parses commands and flags, dispatches to the compiler |
| **Compiler** | `compiler.py` | Central orchestrator -- validation, rendering, output |
| **Schema** | `schema.py` | Pydantic models for target YAML validation |
| **Engine** | `engine.py` | Discovers, loads, and executes templates |
| **Templates** | `template.py` | Base classes and GeneratedFile types |
| **Writers** | `writers.py` | Serializes GeneratedFile objects to disk |
| **State** | `state.py` | Lock files and atomic staging/swap |
| **Helm** | `integrations/helm.py` | Chart resolution (local + registry) and rendering |
| **HCL** | `integrations/hcl.py` | HCL-to-JSON conversion via hcl2json |
| **Compat** | `compat.py` | Legacy target format detection and migration |
| **Config** | `config.py` | Project-level `.geni.yml` configuration |

---

## 3. Compilation Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI as CLI
    participant Compiler as Compiler
    participant Schema as Schema
    participant Compat as Compat
    participant Engine as TemplateEngine
    participant Writers as FileWriter
    participant Atomic as AtomicCompiler
    participant Lock as LockFile

    User->>CLI: geni -t prod
    CLI->>Compiler: compile_target(path)
    Compiler->>Schema: parse YAML
    Schema->>Compat: legacy format?
    Compat-->>Schema: upgrade if needed
    Schema->>Schema: Pydantic validate
    Schema-->>Compiler: TargetManifest

    Compiler->>Compiler: resolve ${{ data.xxx }} refs
    Compiler->>Lock: check input_hash
    Lock-->>Compiler: unchanged? skip / proceed

    Compiler->>Atomic: enter staging context

    loop Each Resource
        Compiler->>Engine: load_and_render(name, template, context)
        alt Python Template (.py)
            Engine->>Engine: importlib load module
            Engine->>Engine: find Template subclass
            Engine->>Engine: instance.render(context)
        else Static Template (.tf/.yml/.json)
            Engine->>Engine: read file content
            Engine->>Engine: substitute ${{ var }} and __var__
            Engine->>Engine: parse to appropriate type
        end
        Engine-->>Compiler: list[GeneratedFile]
        Compiler->>Writers: write_all(files)
    end

    Atomic->>Atomic: atomic swap staging -> output
    Compiler->>Lock: update hashes
    Compiler->>Lock: save .geni-lock.json
    Compiler-->>CLI: list of written paths
    CLI-->>User: [+] Wrote N files
```

Key properties:

- **Validation-first**: target YAML is fully validated before any rendering begins
- **Reference resolution**: `${{ data.xxx }}` refs resolved after validation, before rendering
- **Atomic output**: files written to staging, swapped in one operation -- no partial writes

---

## 4. Template System

### Two Template Modes

```mermaid
flowchart TD
    Engine["TemplateEngine.load_and_render()"]
    Check{File extension?}

    subgraph Static ["Static Template Path"]
        Read["Read file content"]
        Sub["Substitute ${{ var }}<br/>and legacy __var__"]
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

    Engine --> Check
    Check -->|.tf .yml .json| Read
    Check -->|.py| Import
```

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

**Python templates** extend the `Template` base class with full Python logic -- loops, conditionals, API calls, multi-file output. A single Python template can return a list of `GeneratedFile` objects, acting as both template and generator.

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
        +generator: str?
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

Each resource must specify exactly one of `template`, `chart`, or `generator`. The `params` dict is passed to the template at render time, with `${{ data.xxx }}` references resolved from the top-level `data` block.

---

## 6. State Management

### Atomic Compilation

```mermaid
flowchart TD
    Start["Start compile"]
    Stage["Create .geni-staging-*/"]
    Write["Write all files to staging"]
    Check{Success?}
    Swap["Atomic rename<br/>staging -> output"]
    Restore["Restore .terraform/<br/>from backup"]
    Done["Compilation complete"]
    Cleanup["Delete staging<br/>Keep original output"]
    Error["Report error"]

    Start --> Stage --> Write --> Check
    Check -->|Yes| Swap --> Restore --> Done
    Check -->|No| Cleanup --> Error
```

### Incremental Compilation

```mermaid
flowchart LR
    Input["Target YAML"]
    Hash["Compute SHA256"]
    Compare{Hash matches<br/>lock file?}
    Skip["Skip compilation"]
    Recompile["Full recompile"]
    Update["Update .geni-lock.json"]

    Input --> Hash --> Compare
    Compare -->|match| Skip
    Compare -->|mismatch or --force| Recompile --> Update
```

Lock file structure (`.geni-lock.json`):

```json
{
  "version": 1,
  "compiled_at": "2026-03-19T09:17:43+00:00",
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

The `.terraform/` directory is preserved across compilations -- it is backed up before swap and restored after.

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

---

## 8. User Workflows

### New Project

```mermaid
flowchart LR
    Init["geni init"] --> Edit["Edit targets/*.yml<br/>Add templates/"]
    Edit --> Validate["geni validate"]
    Validate --> Compile["geni compile"]
    Compile --> Verify["Review compiled/"]
    Verify --> Apply["terraform apply<br/>kubectl apply"]
```

### Development Cycle

```mermaid
flowchart LR
    Change["Edit template<br/>or target YAML"] --> Diff["geni diff -t prod"]
    Diff --> Review{Changes OK?}
    Review -->|Yes| Compile["geni -t prod"]
    Review -->|No| Change
    Compile --> Commit["git commit"]
```

### CI/CD Pipeline

```mermaid
flowchart LR
    Push["git push"] --> CI["CI Pipeline"]
    CI --> Lint["ruff check"]
    CI --> Test["pytest"]
    CI --> Compile["geni compile --all"]
    Compile --> Plan["terraform plan"]
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
| **Context Manager** | `AtomicCompiler.__enter__/__exit__` | Safe staging/swap with automatic cleanup on failure |
| **Template Method** | `Template.render()` | Base class defines interface, subclasses implement logic |
| **Adapter** | `compat.upgrade_legacy_target` | Transforms old schema format to new without breaking changes |
| **Facade** | `GeniCompiler` | Single interface over engine, writers, state, and integrations |

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
        AC["AtomicCompiler"]
    end

    subgraph Adapter ["Adapter Pattern"]
        CM["compat.py"]
        OLD["Legacy YAML"] --> CM --> NEW["v1alpha1 YAML"]
    end
```

---

## 10. Future: Agentic Architecture (Option A)

An LLM agent sits between the user and Geni, translating natural language requirements into target YAML. The human retains full review authority before any compilation or deployment occurs.

```mermaid
flowchart TD
    User["User<br/>natural language"]
    Agent["LLM Agent<br/>requirement translator"]
    Interview["Clarifying questions"]
    Generate["Generate / modify<br/>target YAML"]
    Review["Human Review<br/>diff in PR"]
    Approved{Approved?}
    Compile["geni compile"]
    Artifacts["Compiled Artifacts"]
    GitOps["GitOps Pipeline<br/>ArgoCD / Flux"]
    Deploy["Infrastructure<br/>Deployed"]

    User --> Agent
    Agent --> Interview --> Agent
    Agent --> Generate --> Review
    Review --> Approved
    Approved -->|yes| Compile
    Approved -->|no| Agent
    Compile --> Artifacts --> GitOps --> Deploy
```

```mermaid
sequenceDiagram
    participant User
    participant Agent as LLM Agent
    participant Git as Git Repository
    participant Geni as Geni Compiler
    participant GitOps as GitOps Controller

    User->>Agent: "Add a Redis cache to staging"
    Agent->>Git: Read existing target YAML
    Git-->>Agent: Current state
    Agent->>Agent: Generate updated target YAML
    Agent->>User: Propose diff for review
    User->>Agent: Approve
    Agent->>Git: Commit updated YAML
    Git->>Geni: CI triggers geni compile
    Geni->>Git: Commit compiled artifacts
    Git->>GitOps: Sync detected
    GitOps-->>User: Redis cache running in staging
```

The agent's job is **requirements to YAML**. Geni's job is **YAML to infrastructure**. The YAML is the contract between them -- human-readable, git-tracked, reviewable. The agent never bypasses the compiler or deploys directly.
