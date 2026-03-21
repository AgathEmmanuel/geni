from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from geni.generator import GeniGenerator
from geni.config import GeniConfig
from geni.errors import GeniError


class TestGenerateTarget:
    def test_generate_static_terraform(self, fixture_dir, tmp_dir):
        fixture = fixture_dir / "simple-terraform"
        config = GeniConfig(
            templates_dir=fixture / "templates",
            targets_dir=fixture,
            generated_dir=tmp_dir,
        )
        generator = GeniGenerator(config)
        target = fixture / "target.yml"

        # Patch output to use tmp_dir
        raw = yaml.safe_load(target.read_text())
        raw["spec"]["output"] = str(tmp_dir / "output")
        patched = tmp_dir / "target.yml"
        patched.write_text(yaml.dump(raw))

        results = generator.generate_target(patched, force=True)
        assert len(results) >= 1
        output_dir = tmp_dir / "output"
        assert output_dir.exists()

        # Check the backend file was created (may be .tf or .tf.json depending on hcl2json)
        backend = output_dir / "backend.tf"
        backend_json = output_dir / "backend.tf.json"
        assert backend.exists() or backend_json.exists()
        content = (backend if backend.exists() else backend_json).read_text()
        assert "my-tf-state" in content
        assert "test" in content

    def test_generate_multi_resource(self, fixture_dir, tmp_dir):
        fixture = fixture_dir / "multi-resource"
        config = GeniConfig(
            templates_dir=fixture / "templates",
            targets_dir=fixture,
            generated_dir=tmp_dir,
        )
        generator = GeniGenerator(config)
        target = fixture / "target.yml"

        raw = yaml.safe_load(target.read_text())
        raw["spec"]["output"] = str(tmp_dir / "output")
        patched = tmp_dir / "target.yml"
        patched.write_text(yaml.dump(raw))

        results = generator.generate_target(patched, force=True)
        assert len(results) == 2

        output_dir = tmp_dir / "output"
        # Files may be .tf or .tf.json depending on hcl2json availability
        backend = output_dir / "backend.tf"
        backend_json = output_dir / "backend.tf.json"
        provider = output_dir / "provider.tf"
        provider_json = output_dir / "provider.tf.json"
        assert backend.exists() or backend_json.exists()
        assert provider.exists() or provider_json.exists()

        backend_content = (backend if backend.exists() else backend_json).read_text()
        provider_content = (provider if provider.exists() else provider_json).read_text()
        assert "multi-test" in backend_content
        assert "multi-test" in provider_content
        assert "us-west1" in provider_content

    def test_generate_kubernetes(self, fixture_dir, tmp_dir):
        fixture = fixture_dir / "simple-kubernetes"
        config = GeniConfig(
            templates_dir=fixture / "templates",
            targets_dir=fixture,
            generated_dir=tmp_dir,
        )
        generator = GeniGenerator(config)
        target = fixture / "target.yml"

        raw = yaml.safe_load(target.read_text())
        raw["spec"]["output"] = str(tmp_dir / "output")
        patched = tmp_dir / "target.yml"
        patched.write_text(yaml.dump(raw))

        results = generator.generate_target(patched, force=True)
        assert len(results) == 1

        ns_file = tmp_dir / "output" / "namespace.yml"
        assert ns_file.exists()
        content = yaml.safe_load(ns_file.read_text())
        assert content["metadata"]["name"] == "monitoring"

    def test_incremental_skip(self, fixture_dir, tmp_dir):
        fixture = fixture_dir / "simple-kubernetes"
        config = GeniConfig(
            templates_dir=fixture / "templates",
            targets_dir=fixture,
            generated_dir=tmp_dir,
        )
        generator = GeniGenerator(config)
        target = fixture / "target.yml"

        raw = yaml.safe_load(target.read_text())
        raw["spec"]["output"] = str(tmp_dir / "output")
        patched = tmp_dir / "target.yml"
        patched.write_text(yaml.dump(raw))

        # First generate
        results1 = generator.generate_target(patched, force=True)
        assert len(results1) >= 1

        # Second generate — should skip
        results2 = generator.generate_target(patched, force=False)
        assert len(results2) == 0

    def test_dry_run(self, fixture_dir, tmp_dir):
        fixture = fixture_dir / "simple-kubernetes"
        config = GeniConfig(
            templates_dir=fixture / "templates",
            targets_dir=fixture,
            generated_dir=tmp_dir,
        )
        generator = GeniGenerator(config)
        target = fixture / "target.yml"

        raw = yaml.safe_load(target.read_text())
        raw["spec"]["output"] = str(tmp_dir / "output")
        patched = tmp_dir / "target.yml"
        patched.write_text(yaml.dump(raw))

        results = generator.generate_target(patched, dry_run=True)
        assert len(results) >= 1


class TestValidateTarget:
    def test_valid(self, fixture_dir):
        fixture = fixture_dir / "simple-terraform"
        config = GeniConfig(
            templates_dir=fixture / "templates",
            targets_dir=fixture,
        )
        generator = GeniGenerator(config)
        manifest = generator.validate_target(fixture / "target.yml")
        assert manifest.metadata.name == "simple-terraform"
