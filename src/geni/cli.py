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


def _do_generate(config, target, dry_run, force):
    """Shared generate logic used by both the default command and the generate subcommand."""
    from geni.generator import GeniGenerator

    generator = GeniGenerator(config)

    if target:
        target_path = config.targets_dir / f"{target}.yml"
        if not target_path.exists():
            click.echo(f"Error: target file not found: {target_path}", err=True)
            sys.exit(1)
        results = generator.generate_target(target_path, dry_run=dry_run, force=force)
        action = "Would write" if dry_run else "Wrote"
        click.echo(f"[+] {action} {len(results)} files for target '{target}'")
    else:
        all_results = generator.generate_all(dry_run=dry_run, force=force)
        for name, paths in all_results.items():
            action = "Would write" if dry_run else "Wrote"
            click.echo(f"[+] {action} {len(paths)} files for target '{name}'")


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="geni")
@click.option("-v", "--verbose", count=True, help="Increase verbosity (-v info, -vv debug)")
@click.option("-t", "--target", default=None, help="Target name to generate (without .yml extension)")
@click.option("--dry-run", is_flag=True, help="Show what would be generated without writing")
@click.option("--force", is_flag=True, help="Force regeneration even if unchanged")
@click.pass_context
def main(ctx, verbose, target, dry_run, force):
    """geni -- Python-powered infrastructure-as-code generator.

    When invoked without a subcommand, generates targets directly:

        geni -t prod          generate a single target

        geni                  generate all targets

        geni -t prod --dry-run
    """
    setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["config"] = GeniConfig.load()
    ctx.obj["verbose"] = verbose

    # If no subcommand was given, run generate as the default action
    if ctx.invoked_subcommand is None:
        try:
            _do_generate(ctx.obj["config"], target, dry_run, force)
        except GeniError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)


@main.command(name="generate")
@click.option("-t", "--target", help="Target name to generate (without .yml extension)")
@click.option("--all", "generate_all", is_flag=True, help="Generate all targets")
@click.option("--dry-run", is_flag=True, help="Show what would be generated without writing")
@click.option("--force", is_flag=True, help="Force regeneration even if unchanged")
def generate(target, generate_all, dry_run, force):
    """Generate infrastructure artifacts from target YAML."""
    config = click.get_current_context().obj["config"]
    try:
        _do_generate(config, target, dry_run, force)
    except GeniError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# Short alias: geni g -t dev
main.add_command(generate, name="g")


@main.command()
@click.option("-t", "--target", help="Target name to validate")
@click.option("--all", "validate_all", is_flag=True, help="Validate all targets")
def validate(target, validate_all):
    """Validate target YAML files against the schema."""
    from geni.generator import GeniGenerator

    config = click.get_current_context().obj["config"]
    generator = GeniGenerator(config)

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
            generator.validate_target(t)
            click.echo(f"[+] Valid: {t.stem}")
        except GeniError as e:
            click.echo(f"[!] Invalid: {t.stem} -- {e}", err=True)
            errors += 1

    if errors:
        sys.exit(1)


@main.command()
@click.option("-t", "--target", required=True, help="Target name to diff")
def diff(target):
    """Show what would change if a target were regenerated."""
    from geni.generator import GeniGenerator

    config = click.get_current_context().obj["config"]
    generator = GeniGenerator(config)

    target_path = config.targets_dir / f"{target}.yml"
    if not target_path.exists():
        click.echo(f"Error: target file not found: {target_path}", err=True)
        sys.exit(1)

    try:
        diff_output = generator.diff_target(target_path)
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

    dirs = ["targets", "templates/terraform", "templates/kubernetes", "generated"]
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
  output: generated/terraform/example
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
generated_dir: generated
""")

    click.echo(f"[+] Initialized geni project in {project.resolve()}")
    click.echo("    - targets/example.yml (example target)")
    click.echo("    - templates/terraform/backend.tf (example template)")
    click.echo("    Run: geni generate -t example")
