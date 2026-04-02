from __future__ import annotations

import pytest
import yaml
from pathlib import Path

from geni.schema import (
    TargetManifest,
    Metadata,
    Spec,
    ResourceDef,
    ChartSource,
    LocalChart,
    RegistryChart,
    load_target,
    resolve_refs,
)
from geni.errors import SchemaValidationError


class TestMetadata:
    def test_minimal(self):
        m = Metadata(name="test")
        assert m.name == "test"
        assert m.labels == {}

    def test_with_labels(self):
        m = Metadata(name="prod", labels={"env": "production"})
        assert m.labels["env"] == "production"


class TestChartSource:
    def test_local_chart(self):
        cs = ChartSource.model_validate({"path": "helm/charts/my-chart"})
        assert cs.is_local
        assert cs.path == "helm/charts/my-chart"

    def test_registry_chart(self):
        cs = ChartSource.model_validate({
            "repo": "https://charts.example.com",
            "name": "my-chart",
            "version": "1.0.0",
        })
        assert not cs.is_local
        assert cs.repo == "https://charts.example.com"
        assert cs.name == "my-chart"
        assert cs.version == "1.0.0"

    def test_invalid_chart_raises(self):
        with pytest.raises(SchemaValidationError):
            ChartSource.model_validate({"foo": "bar"})


class TestResourceDef:
    def test_template_resource(self):
        r = ResourceDef(template="terraform/backend.tf", params={"bucket": "x"})
        assert r.template == "terraform/backend.tf"
        assert r.chart is None

    def test_chart_resource(self):
        r = ResourceDef(
            chart={"path": "helm/charts/foo"},
            values="helm/values/foo.yml",
            params={"namespace": "default"},
        )
        assert r.chart is not None
        assert r.template is None

    def test_no_source_raises(self):
        with pytest.raises(SchemaValidationError):
            ResourceDef(params={"x": "y"})

    def test_multiple_sources_raises(self):
        with pytest.raises(SchemaValidationError):
            ResourceDef(template="a.tf", chart={"path": "charts/foo"})


class TestTargetManifest:
    def test_valid_manifest(self):
        raw = {
            "apiVersion": "geni.io/v1alpha1",
            "kind": "Target",
            "metadata": {"name": "test"},
            "spec": {
                "data": {"project": "my-project"},
                "output": "compiled/test",
                "resources": {
                    "backend": {
                        "template": "terraform/backend.tf",
                        "params": {"bucket": "my-bucket"},
                    }
                },
            },
        }
        m = TargetManifest.model_validate(raw)
        assert m.metadata.name == "test"
        assert m.spec.data["project"] == "my-project"
        assert "backend" in m.spec.resources

    def test_invalid_api_version(self):
        raw = {
            "apiVersion": "geni.io/v2",
            "kind": "Target",
            "metadata": {"name": "test"},
            "spec": {"output": "out", "resources": {"a": {"template": "a.tf"}}},
        }
        with pytest.raises(Exception):
            TargetManifest.model_validate(raw)

    def test_invalid_kind(self):
        raw = {
            "apiVersion": "geni.io/v1alpha1",
            "kind": "Wrong",
            "metadata": {"name": "test"},
            "spec": {"output": "out", "resources": {"a": {"template": "a.tf"}}},
        }
        with pytest.raises(Exception):
            TargetManifest.model_validate(raw)

    def test_extra_fields_allowed(self):
        raw = {
            "apiVersion": "geni.io/v1alpha1",
            "kind": "Target",
            "metadata": {"name": "test"},
            "spec": {"output": "out", "resources": {"a": {"template": "a.tf"}}},
            "x-custom": "value",
        }
        m = TargetManifest.model_validate(raw)
        assert m.metadata.name == "test"


class TestResolveRefs:
    def test_simple_data_ref(self):
        result = resolve_refs("${{ data.project }}", {"project": "my-proj"})
        assert result == "my-proj"

    def test_preserves_type(self):
        data = {"count": 5}
        result = resolve_refs("${{ data.count }}", data)
        assert result == 5

    def test_nested_dict(self):
        data = {"project": "p1"}
        val = {"name": "${{ data.project }}", "nested": {"x": "${{ data.project }}"}}
        result = resolve_refs(val, data)
        assert result == {"name": "p1", "nested": {"x": "p1"}}

    def test_list(self):
        data = {"env": "prod"}
        result = resolve_refs(["${{ data.env }}", "static"], data)
        assert result == ["prod", "static"]

    def test_no_ref(self):
        result = resolve_refs("no refs here", {"project": "x"})
        assert result == "no refs here"

    def test_missing_ref_passthrough(self):
        result = resolve_refs("${{ data.missing }}", {"project": "x"})
        assert result == "${{ data.missing }}"


class TestLoadTarget:
    def test_load_valid_target(self, fixture_dir):
        target_path = fixture_dir / "simple-terraform" / "target.yml"
        manifest = load_target(target_path)
        assert manifest.metadata.name == "simple-terraform"
        assert "backend" in manifest.spec.resources

    def test_load_nonexistent_raises(self, tmp_dir):
        with pytest.raises(SchemaValidationError):
            load_target(tmp_dir / "nonexistent.yml")
