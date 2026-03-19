from __future__ import annotations

import yaml
from pathlib import Path

import pytest

from geni.compat import is_legacy_format, upgrade_legacy_target, migrate_target_file


class TestIsLegacyFormat:
    def test_legacy(self):
        assert is_legacy_format({"data": {"project": "x"}, "compiled": "out"})

    def test_new_format(self):
        assert not is_legacy_format({"apiVersion": "geni.io/v1alpha1"})


class TestUpgradeLegacyTarget:
    def test_basic_upgrade(self):
        old = {
            "data": {"project": "my-proj"},
            "compiled": "compiled/terraform/my-proj",
            "resources": {
                "backend": {
                    "template": "terraform/backend.tf",
                    "parameter": {"bucket": "my-bucket"},
                }
            },
        }
        result = upgrade_legacy_target(old, "my-proj.yml")
        assert result["apiVersion"] == "geni.io/v1alpha1"
        assert result["kind"] == "Target"
        assert result["metadata"]["name"] == "my-proj"
        assert result["spec"]["data"]["project"] == "my-proj"
        assert result["spec"]["output"] == "compiled/terraform/my-proj"
        assert result["spec"]["resources"]["backend"]["params"]["bucket"] == "my-bucket"
        assert "parameter" not in result["spec"]["resources"]["backend"]

    def test_component_to_template(self):
        old = {
            "data": {},
            "compiled": "out",
            "resources": {
                "svc": {
                    "component": "components/services.py",
                    "parameter": {"x": "y"},
                }
            },
        }
        result = upgrade_legacy_target(old, "test.yml")
        assert result["spec"]["resources"]["svc"]["template"] == "components/services.py"
        assert "component" not in result["spec"]["resources"]["svc"]

    def test_chart_string_to_dict(self):
        old = {
            "data": {},
            "compiled": "out",
            "resources": {
                "metrics": {
                    "chart": "helm/charts/kube-state-metrics",
                    "value": "helm/values/values.yml",
                    "parameter": {"namespace": "monitoring"},
                }
            },
        }
        result = upgrade_legacy_target(old, "test.yml")
        chart = result["spec"]["resources"]["metrics"]["chart"]
        assert isinstance(chart, dict)
        assert chart["path"] == "helm/charts/kube-state-metrics"
        assert result["spec"]["resources"]["metrics"]["values"] == "helm/values/values.yml"
        assert "value" not in result["spec"]["resources"]["metrics"]


class TestMigrateTargetFile:
    def test_migrate_file(self, tmp_dir):
        target = tmp_dir / "old.yml"
        target.write_text(yaml.dump({
            "data": {"project": "p1"},
            "compiled": "out",
            "resources": {
                "backend": {
                    "template": "tf/backend.tf",
                    "parameter": {"bucket": "b1"},
                }
            },
        }))

        migrate_target_file(target)

        result = yaml.safe_load(target.read_text())
        assert result["apiVersion"] == "geni.io/v1alpha1"
        assert result["spec"]["resources"]["backend"]["params"]["bucket"] == "b1"

    def test_skip_already_migrated(self, tmp_dir):
        target = tmp_dir / "new.yml"
        content = yaml.dump({
            "apiVersion": "geni.io/v1alpha1",
            "kind": "Target",
            "metadata": {"name": "test"},
            "spec": {"output": "out", "resources": {"a": {"template": "a.tf"}}},
        })
        target.write_text(content)

        migrate_target_file(target)
        assert target.read_text() == content  # unchanged
