# 🧠 geni — Generic Infrastructure Generator

**geni** is a lightweight, template-driven infrastructure generation tool that simplifies the creation and management of Kubernetes resources, Helm charts, Terraform files, and more — all driven by a single declarative YAML configuration.

---

## 🚀 Features

- 📁 Compile multiple resources into a unified structure.
- 🧠 Supports Helm charts, Terraform HCL/JSON, and raw Kubernetes YAML.
- 🎛 Replace placeholders like `__var__` in Helm values files.
- 📌 Built-in support for components, templates, and parameter overrides.
- 🔀 Automatically splits or merges multi-document YAMLs.

---

## 📂 Folder Structure

```

geni/
├── compiled
│   ├── kubernetes
│   │   └── example-monitoring
│   │       ├── kube-state-metrics
│   │       ├── namespace.yml
│   │       └── opentelemetry-operator
│   └── terraform
│       └── example-prod-infra
│           ├── backend.tf.json
│           ├── buckets.tf.json
│           ├── cluster_autopilot.tf.json
│           ├── instance.tf.json
│           ├── provider.tf.json
│           └── services.tf.json
├── components
│   ├── enable_services.py
│   └── random_bucket.py
├── geni.py
├── README.md
├── targets
│   ├── example-monitoring.yml
│   └── example-prod-infra.yml
├── templates
│   ├── helm
│   │   ├── charts
│   │   │   ├── kube-state-metrics
│   │   │   │   ├── Chart.yaml
│   │   │   │   ├── README.md
│   │   │   │   ├── templates
│   │   │   │   └── values.yaml
│   │   │   └── opentelemetry-operator
│   │   └── values
│   │       ├── kube-state-metrics-values.yml
│   │       └── opentelemetry-operator-values.yml
│   ├── kubernetes
│   │   ├── cert-manager.yml
│   │   ├── deployment.yml
│   │   └── namespace.yml
│   ├── scripts
│   ├── terraform_tf
│   │   ├── backend.tf
│   │   ├── bucket.tf
│   │   ├── cluster_autopilot.tf
│   │   ├── instance.tf
│   │   ├── provider.tf
│   │   └── service.tf
│   └── terraform_tf_json
│       ├── backend.tf.json
│       ├── bucket.tf.json
│       ├── cluster_autopilot.tf.json
│       ├── instance.tf.json
│       ├── provider.tf.json
│       └── service.tf.json
└── utils
    ├── base.py
    ├── configure.py

```

---

## 📄 Target File Format

A target YAML defines all the resources you want to generate for a specific project/environment.

```yaml
data:
  project: my-observability-stack

compiled: compiled/kubernetes/observability

resources:
  prometheus:
    chart: charts/prometheus
    value: values/prometheus-values.yml
    parameter:
      alertmanager_enabled: true
      podSecurityPolicy: false

  grafana:
    chart: charts/grafana
    value: values/grafana-values.yml
    parameter:
      adminUser: "__grafana_admin__"
      adminPassword: "__grafana_password__"

  alerts:
    template: kubernetes/alert-rules.yml
    parameter:
      severity: high
```

---

## 🤩 Template Syntax

In any template or values file:

```yaml
alertmanager:
  enabled: __alertmanager_enabled__

metadata:
  name: __project__-alertmanager
```

These placeholders will be replaced during rendering.

---

## ⚙️ Usage

### 1. Install dependencies (optional)

Install Helm.
Install hcl2json. 
https://github.com/tmccombs/hcl2json


### 2. Compile a target file

```bash
python geni.py
python geni.py -t example-monitoring

```

The output is generated in the path defined under `compiled:` in your target file.

---

## 🔨 Supported Resource Types

### ✅ Helm Charts

```yaml
prometheus:
  chart: charts/prometheus
  value: values/prometheus-values.yml
  parameter:
    podSecurityPolicy: true
```

➡️ Will run:

```bash
helm template prometheus ./charts/prometheus --output-dir compiled/... -f values/prometheus-values.yml
```

### ✅ Templates (YAML or Terraform)

```yaml
alerts:
  template: kubernetes/alert-rules.yml
  parameter:
    severity: critical
```


### ✅ Components

A component is a reusable Python function or CLI-integrated script.

```yaml
some-module:
  component: components/my-generator
  parameter:
    foo: bar
```

---

## 📘 Multi-Document YAML Support

Templates with multiple YAML documents (`---`) are automatically detected. You can choose whether to:

- Output as a single file with `---` separation.
- Or write each document separately (`resource-0.yml`, `resource-1.yml`).

By default, they are **preserved as a single file**.

---

## 🤫 Clean Compiled Output

Each compile run clears the previous output path (defined under `compiled:`) before writing new files, ensuring clean state.

---

## 💡 Use Cases

- GitOps pipelines (Argo CD / FluxCD)
- Platform engineering & golden templates
- Infra-as-Code for observability and platform services
- Custom Terraform + K8s + Helm generators

---

## 🤝 Contributing

1. Fork the repo
2. Add your template or component
3. Run `python geni.py compile targets/dev.yml`
4. Create a PR 🚀

---

## 📜 License

MIT — free to use and extend.

