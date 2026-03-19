from __future__ import annotations

import json
from pathlib import Path

import pytest

from geni.engine import TemplateEngine
from geni.template import RenderContext, GeneratedFile, Template, TerraformJSON
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


class TestLegacySubstitution:
    def test_legacy_double_underscore(self, tmp_dir):
        """Test that __var__ legacy syntax is still supported."""
        template_dir = tmp_dir / "templates"
        template_dir.mkdir()
        tf_dir = template_dir / "terraform"
        tf_dir.mkdir()
        (tf_dir / "test.tf").write_text('bucket = "__bucket_name__"')

        engine = TemplateEngine(template_dir)
        ctx = make_context(
            params={"bucket_name": "my-bucket"},
            templates_dir=template_dir,
            output_dir=tmp_dir,
        )
        results = engine.load_and_render("test", "terraform/test.tf", ctx)
        assert 'my-bucket' in results[0].content


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
