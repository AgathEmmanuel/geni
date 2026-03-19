from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from geni import __version__
from geni.config import GeniConfig
from geni.errors import GeniError


def setup_logging(verbosity: int):
    level = {0: logging.WARNING, 1: logging.INFO}.get(verbosity, logging.DEBUG)
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(message)s" if level > logging.DEBUG else "%(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )


def _do_compile(config, target, dry_run, force):
    """Shared compile logic used by both the default command and the compile subcommand."""
    from geni.compiler import GeniCompiler

    compiler = GeniCompiler(config)

    if target:
        target_path = config.targets_dir / f"{target}.yml"
        if not target_path.exists():
            click.echo(f"Error: target file not found: {target_path}", err=True)
            sys.exit(1)
        results = compiler.compile_target(target_path, dry_run=dry_run, force=force)
        action = "Would write" if dry_run else "Wrote"
        click.echo(f"[+] {action} {len(results)} files for target '{target}'")
    else:
        all_results = compiler.compile_all(dry_run=dry_run, force=force)
        for name, paths in all_results.items():
            action = "Would write" if dry_run else "Wrote"
            click.echo(f"[+] {action} {len(paths)} files for target '{name}'")


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="geni")
@click.option("-v", "--verbose", count=True, help="Increase verbosity (-v info, -vv debug)")
@click.option("-t", "--target", default=None, help="Target name to compile (without .yml extension)")
@click.option("--dry-run", is_flag=True, help="Show what would be compiled without writing")
@click.option("--force", is_flag=True, help="Force recompilation even if unchanged")
@click.pass_context
def main(ctx, verbose, target, dry_run, force):
    """geni -- Python-powered infrastructure-as-code compiler.

    When invoked without a subcommand, compiles targets directly:

        geni -t prod          compile a single target

        geni                  compile all targets

        geni -t prod --dry-run
    """
    setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["config"] = GeniConfig.load()
    ctx.obj["verbose"] = verbose

    # If no subcommand was given, run compile as the default action
    if ctx.invoked_subcommand is None:
        try:
            _do_compile(ctx.obj["config"], target, dry_run, force)
        except GeniError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)


@main.command()
@click.option("-t", "--target", help="Target name to compile (without .yml extension)")
@click.option("--all", "compile_all", is_flag=True, help="Compile all targets")
@click.option("--dry-run", is_flag=True, help="Show what would be compiled without writing")
@click.option("--force", is_flag=True, help="Force recompilation even if unchanged")
def compile(target, compile_all, dry_run, force):
    """Compile target YAML into infrastructure artifacts."""
    config = click.get_current_context().obj["config"]
    try:
        _do_compile(config, target, dry_run, force)
    except GeniError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("-t", "--target", help="Target name to validate")
@click.option("--all", "validate_all", is_flag=True, help="Validate all targets")
def validate(target, validate_all):
    """Validate target YAML files against the schema."""
    from geni.compiler import GeniCompiler

    config = click.get_current_context().obj["config"]
    compiler = GeniCompiler(config)

    targets = []
    if target:
        targets = [config.targets_dir / f"{target}.yml"]
    else:
        targets = sorted(config.targets_dir.glob("*.yml"))

    errors = 0
    for t in targets:
        if not t.exists():
            click.echo(f"[!] Not found: {t}", err=True)
            errors += 1
            continue
        try:
            compiler.validate_target(t)
            click.echo(f"[+] Valid: {t.stem}")
        except GeniError as e:
            click.echo(f"[!] Invalid: {t.stem} -- {e}", err=True)
            errors += 1

    if errors:
        sys.exit(1)


@main.command()
@click.option("-t", "--target", required=True, help="Target name to diff")
def diff(target):
    """Show what would change if a target were recompiled."""
    from geni.compiler import GeniCompiler

    config = click.get_current_context().obj["config"]
    compiler = GeniCompiler(config)

    target_path = config.targets_dir / f"{target}.yml"
    if not target_path.exists():
        click.echo(f"Error: target file not found: {target_path}", err=True)
        sys.exit(1)

    try:
        diff_output = compiler.diff_target(target_path)
        if diff_output:
            click.echo(diff_output)
        else:
            click.echo(f"No changes for target '{target}'")
    except GeniError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--dir", "project_dir", default=".", help="Directory to initialize")
def init(project_dir):
    """Initialize a new geni project with example files."""
    project = Path(project_dir)

    dirs = ["targets", "templates/terraform", "templates/kubernetes", "compiled"]
    for d in dirs:
        (project / d).mkdir(parents=True, exist_ok=True)

    # Example target
    example_target = project / "targets" / "example.yml"
    if not example_target.exists():
        example_target.write_text("""apiVersion: geni.io/v1alpha1
kind: Target
metadata:
  name: example
  labels:
    environment: dev
spec:
  data:
    project: my-project
    region: us-central1
  output: compiled/terraform/example
  resources:
    backend:
      template: terraform/backend.tf
      params:
        bucket_name: my-terraform-state
        tfstate_prefix: example
""")

    # Example static template
    example_template = project / "templates" / "terraform" / "backend.tf"
    if not example_template.exists():
        example_template.write_text("""terraform {
  backend "gcs" {
    bucket = "${{ bucket_name }}"
    prefix = "${{ tfstate_prefix }}"
  }
}
""")

    # Example .geni.yml
    config_file = project / ".geni.yml"
    if not config_file.exists():
        config_file.write_text("""templates_dir: templates
targets_dir: targets
compiled_dir: compiled
""")

    click.echo(f"[+] Initialized geni project in {project.resolve()}")
    click.echo("    - targets/example.yml (example target)")
    click.echo("    - templates/terraform/backend.tf (example template)")
    click.echo("    Run: geni -t example")


@main.command()
@click.option("--targets", is_flag=True, help="Migrate target files to v1alpha1 format")
def migrate(targets):
    """Migrate legacy format files to the current schema."""
    from geni.compat import migrate_target_file

    config = click.get_current_context().obj["config"]

    if targets:
        for t in sorted(config.targets_dir.glob("*.yml")):
            try:
                migrate_target_file(t)
            except Exception as e:
                click.echo(f"[!] Failed to migrate {t.name}: {e}", err=True)
    else:
        click.echo("Specify --targets to migrate target YAML files")
