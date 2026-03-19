from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from geni.cli import main


@pytest.fixture
def runner():
    return CliRunner()


class TestVersion:
    def test_version(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestInit:
    def test_init_creates_structure(self, runner, tmp_dir):
        result = runner.invoke(main, ["init", "--dir", str(tmp_dir)])
        assert result.exit_code == 0
        assert (tmp_dir / "targets" / "example.yml").exists()
        assert (tmp_dir / "templates" / "terraform" / "backend.tf").exists()
        assert (tmp_dir / ".geni.yml").exists()


class TestValidate:
    def test_validate_valid_target(self, runner, fixture_dir, tmp_dir):
        fixture = fixture_dir / "simple-kubernetes"
        project_dir = tmp_dir / "project"
        project_dir.mkdir()

        targets_dir = project_dir / "targets"
        targets_dir.mkdir()
        raw = yaml.safe_load((fixture / "target.yml").read_text())
        (targets_dir / "simple-kubernetes.yml").write_text(yaml.dump(raw))

        templates_dir = project_dir / "templates"
        shutil.copytree(fixture / "templates", templates_dir)

        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            result = runner.invoke(main, ["validate", "-t", "simple-kubernetes"])
            assert result.exit_code == 0
            assert "Valid" in result.output
        finally:
            os.chdir(old_cwd)


class TestCompile:
    def _setup_project(self, fixture_dir, tmp_dir):
        fixture = fixture_dir / "simple-kubernetes"
        project_dir = tmp_dir / "project"
        project_dir.mkdir()

        targets_dir = project_dir / "targets"
        targets_dir.mkdir()
        raw = yaml.safe_load((fixture / "target.yml").read_text())
        raw["spec"]["output"] = str(tmp_dir / "compiled")
        (targets_dir / "simple-kubernetes.yml").write_text(yaml.dump(raw))

        templates_dir = project_dir / "templates"
        shutil.copytree(fixture / "templates", templates_dir)
        return project_dir

    def test_compile_subcommand(self, runner, fixture_dir, tmp_dir):
        """geni compile -t works as a subcommand."""
        project_dir = self._setup_project(fixture_dir, tmp_dir)
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            result = runner.invoke(main, ["compile", "-t", "simple-kubernetes"])
            assert result.exit_code == 0
            assert "Wrote" in result.output
        finally:
            os.chdir(old_cwd)

    def test_compile_default(self, runner, fixture_dir, tmp_dir):
        """geni -t works without the compile subcommand."""
        project_dir = self._setup_project(fixture_dir, tmp_dir)
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            result = runner.invoke(main, ["-t", "simple-kubernetes"])
            assert result.exit_code == 0
            assert "Wrote" in result.output
        finally:
            os.chdir(old_cwd)
