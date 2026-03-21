from __future__ import annotations

import json
from pathlib import Path

import pytest

from geni.engine import TemplateEngine
from geni.template import RenderContext, GeneratedFile, Template, TerraformJSON, TerraformHCL
from geni.errors import TemplateError


@pytest.fixture
def simple_tf_fixture(fixture_dir):
    return fixture_dir / "simple-terraform"


@pytest.fixture
def simple_k8s_fixture(fixture_dir):
    return fixture_dir / "simple-kubernetes"


@pytest.fixture
def python_template_fixture(fixture_dir):
    return fixture_dir / "python-template"


def make_context(params=None, data=None, templates_dir=None, output_dir=None):
    return RenderContext(
        params=params or {},
        data=data or {},
        resources={},
        templates_dir=templates_dir or Path("."),
        output_dir=output_dir or Path("."),
    )


class TestStaticTemplateRendering:
    def test_hcl_substitution(self, simple_tf_fixture, tmp_dir):
        engine = TemplateEngine(simple_tf_fixture / "templates")
        ctx = make_context(
            params={"bucket_name": "my-bucket", "tfstate_prefix": "prod"},
            templates_dir=simple_tf_fixture / "templates",
            output_dir=tmp_dir,
        )
        results = engine.load_and_render("backend", "terraform/backend.tf", ctx)
        assert len(results) == 1
        assert results[0].file_type == "tf"
        assert "my-bucket" in results[0].content
        assert "prod" in results[0].content

    def test_yaml_substitution(self, simple_k8s_fixture, tmp_dir):
        engine = TemplateEngine(simple_k8s_fixture / "templates")
        ctx = make_context(
            params={"namespace": "monitoring"},
            templates_dir=simple_k8s_fixture / "templates",
            output_dir=tmp_dir,
        )
        results = engine.load_and_render("namespace", "kubernetes/namespace.yml", ctx)
        assert len(results) == 1
        assert results[0].file_type == "yaml"
        assert results[0].content["metadata"]["name"] == "monitoring"

    def test_data_ref_substitution(self, simple_tf_fixture, tmp_dir):
        engine = TemplateEngine(simple_tf_fixture / "templates")
        ctx = make_context(
            params={"bucket_name": "${{ data.project }}", "tfstate_prefix": "test"},
            data={"project": "resolved-project"},
            templates_dir=simple_tf_fixture / "templates",
            output_dir=tmp_dir,
        )
        # Note: ${{ data.xxx }} in params are resolved before reaching engine,
        # but the engine also handles ${{ data.xxx }} in file content
        results = engine.load_and_render("backend", "terraform/backend.tf", ctx)
        assert len(results) == 1

    def test_missing_template_raises(self, tmp_dir):
        engine = TemplateEngine(tmp_dir)
        ctx = make_context(templates_dir=tmp_dir, output_dir=tmp_dir)
        with pytest.raises(TemplateError):
            engine.load_and_render("missing", "nonexistent.tf", ctx)


class TestPythonTemplateRendering:
    def test_python_template(self, python_template_fixture, tmp_dir):
        engine = TemplateEngine(python_template_fixture / "templates")
        ctx = make_context(
            params={
                "project_name": "test-project",
                "services": ["compute.googleapis.com", "iam.googleapis.com"],
            },
            data={"project": "test-project"},
            templates_dir=python_template_fixture / "templates",
            output_dir=tmp_dir,
        )
        results = engine.load_and_render("services", "terraform/services.py", ctx)
        assert len(results) == 1
        assert results[0].file_type == "tf.json"
        content = results[0].content
        assert "resource" in content

    def test_path_traversal_blocked(self, simple_tf_fixture, tmp_dir):
        engine = TemplateEngine(simple_tf_fixture / "templates")
        ctx = make_context(
            templates_dir=simple_tf_fixture / "templates",
            output_dir=tmp_dir,
        )
        with pytest.raises(TemplateError):
            engine.load_and_render("evil", "../../geni.py", ctx)


class TestSubstitute:
    def test_new_style(self):
        engine = TemplateEngine(Path("."))
        ctx = make_context(params={"name": "hello"}, data={"project": "p1"})
        result = engine._substitute("name=${{ name }}, project=${{ data.project }}", ctx)
        assert result == "name=hello, project=p1"

    def test_dict_serialization(self):
        engine = TemplateEngine(Path("."))
        ctx = make_context(params={"config": {"key": "value"}})
        result = engine._substitute("config=${{ config }}", ctx)
        assert '"key": "value"' in result

    def test_unresolved_passthrough(self):
        engine = TemplateEngine(Path("."))
        ctx = make_context(params={})
        result = engine._substitute("val=${{ unknown }}", ctx)
        assert result == "val=${{ unknown }}"


class TestRenderStatic:
    def test_render_static_hcl(self, tmp_dir):
        """render_static substitutes placeholders and returns string."""
        tpl_dir = tmp_dir / "templates" / "terraform"
        tpl_dir.mkdir(parents=True)
        (tpl_dir / "bucket.tf").write_text(
            'resource "google_storage_bucket" "${{ name }}" {\n'
            '  name    = "${{ bucket_name }}"\n'
            '  project = "${{ project }}"\n'
            "}\n"
        )

        ctx = make_context(templates_dir=tmp_dir / "templates")
        rendered = ctx.render_static("terraform/bucket.tf", {
            "name": "assets",
            "bucket_name": "my-proj-assets",
            "project": "my-proj",
        })
        assert '"assets"' in rendered
        assert '"my-proj-assets"' in rendered
        assert '"my-proj"' in rendered

    def test_render_static_loop(self, tmp_dir):
        """Python template can loop over render_static to produce N resources."""
        tpl_dir = tmp_dir / "templates" / "terraform"
        tpl_dir.mkdir(parents=True)
        (tpl_dir / "bucket.tf").write_text(
            'resource "google_storage_bucket" "${{ resource_name }}" {\n'
            '  name = "${{ bucket_name }}"\n'
            "}\n"
        )

        ctx = make_context(
            params={
                "project": "my-proj",
                "buckets": [
                    {"name": "assets"},
                    {"name": "backups"},
                ],
            },
            templates_dir=tmp_dir / "templates",
        )

        blocks = []
        for bucket in ctx.params["buckets"]:
            hcl = ctx.render_static("terraform/bucket.tf", {
                "resource_name": bucket["name"],
                "bucket_name": f"{ctx.params['project']}-{bucket['name']}",
            })
            blocks.append(hcl)

        combined = "\n".join(blocks)
        result = TerraformHCL("storage.tf", combined)

        assert result.file_type == "tf"
        assert '"assets"' in result.content
        assert '"backups"' in result.content
        assert "my-proj-assets" in result.content
        assert "my-proj-backups" in result.content

    def test_render_static_json(self, tmp_dir):
        """render_static_json returns a parsed dict from a .tf.json template."""
        tpl_dir = tmp_dir / "templates" / "terraform"
        tpl_dir.mkdir(parents=True)
        (tpl_dir / "bucket.tf.json").write_text(json.dumps({
            "resource": {
                "google_storage_bucket": {
                    "__PLACEHOLDER__": {
                        "name": "${{ bucket_name }}",
                        "project": "${{ project }}",
                        "location": "${{ region }}",
                    }
                }
            }
        }))

        ctx = make_context(templates_dir=tmp_dir / "templates")
        result = ctx.render_static_json("terraform/bucket.tf.json", {
            "bucket_name": "my-proj-assets",
            "project": "my-proj",
            "region": "us-central1",
        })

        assert isinstance(result, dict)
        bucket = result["resource"]["google_storage_bucket"]["__PLACEHOLDER__"]
        assert bucket["name"] == "my-proj-assets"
        assert bucket["project"] == "my-proj"
        assert bucket["location"] == "us-central1"

    def test_render_static_json_merge(self, tmp_dir):
        """Multiple render_static_json calls can be merged into one TerraformJSON."""
        tpl_dir = tmp_dir / "templates" / "terraform"
        tpl_dir.mkdir(parents=True)
        (tpl_dir / "bucket.tf.json").write_text(json.dumps({
            "resource": {
                "google_storage_bucket": {
                    "${{ resource_name }}": {
                        "name": "${{ bucket_name }}",
                        "project": "${{ project }}",
                    }
                }
            }
        }))

        ctx = make_context(templates_dir=tmp_dir / "templates")
        buckets = [
            {"name": "assets", "project": "my-proj"},
            {"name": "backups", "project": "my-proj"},
        ]

        merged = {}
        for bucket in buckets:
            tf = ctx.render_static_json("terraform/bucket.tf.json", {
                "resource_name": bucket["name"],
                "bucket_name": f"{bucket['project']}-{bucket['name']}",
                "project": bucket["project"],
            })
            # Merge the bucket resources
            for rtype, resources in tf.get("resource", {}).items():
                merged.setdefault(rtype, {}).update(resources)

        result = TerraformJSON("storage.tf.json", {"resource": merged})
        gcs = result.content["resource"]["google_storage_bucket"]
        assert "assets" in gcs
        assert "backups" in gcs
        assert gcs["assets"]["name"] == "my-proj-assets"
        assert gcs["backups"]["name"] == "my-proj-backups"

    def test_render_static_missing_file(self, tmp_dir):
        """render_static raises FileNotFoundError for missing templates."""
        ctx = make_context(templates_dir=tmp_dir)
        with pytest.raises(FileNotFoundError):
            ctx.render_static("nonexistent.tf", {})

    def test_render_static_unresolved_placeholder(self, tmp_dir):
        """Unresolved placeholders are left as-is."""
        tpl_dir = tmp_dir / "templates"
        tpl_dir.mkdir()
        (tpl_dir / "test.tf").write_text('name = "${{ unknown }}"')

        ctx = make_context(templates_dir=tpl_dir)
        result = ctx.render_static("test.tf", {})
        assert "${{ unknown }}" in result
