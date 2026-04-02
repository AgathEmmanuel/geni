from __future__ import annotations

import json
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


def _output_result(data: dict, output_format: str):
    """Output result as JSON or human-readable text."""
    if output_format == "json":
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        # Let callers handle text output
        return False
    return True


def _do_generate(config, target, dry_run, force, output_format="text"):
    """Shared generate logic used by both the default command and the generate subcommand."""
    from geni.generator import GeniGenerator

    generator = GeniGenerator(config)

    if target:
        target_path = config.targets_dir / f"{target}.yml"
        if not target_path.exists():
            if output_format == "json":
                _output_result({"error": f"target file not found: {target_path}", "success": False}, "json")
                sys.exit(1)
            click.echo(f"Error: target file not found: {target_path}", err=True)
            sys.exit(1)
        results = generator.generate_target(target_path, dry_run=dry_run, force=force)
        action = "Would write" if dry_run else "Wrote"

        if output_format == "json":
            _output_result({
                "success": True,
                "target": target,
                "action": "dry_run" if dry_run else "generate",
                "files_written": len(results),
                "files": [str(p) for p in results],
            }, "json")
        else:
            click.echo(f"[+] {action} {len(results)} files for target '{target}'")
    else:
        all_results = generator.generate_all(dry_run=dry_run, force=force)

        if output_format == "json":
            targets_out = {}
            for name, paths in all_results.items():
                targets_out[name] = {
                    "files_written": len(paths),
                    "files": [str(p) for p in paths],
                }
            _output_result({
                "success": True,
                "action": "dry_run" if dry_run else "generate",
                "targets": targets_out,
            }, "json")
        else:
            for name, paths in all_results.items():
                action = "Would write" if dry_run else "Wrote"
                click.echo(f"[+] {action} {len(paths)} files for target '{name}'")


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="geni")
@click.option("-v", "--verbose", count=True, help="Increase verbosity (-v info, -vv debug)")
@click.option("-t", "--target", default=None, help="Target name to generate (without .yml extension)")
@click.option("--dry-run", is_flag=True, help="Show what would be generated without writing")
@click.option("--force", is_flag=True, help="Force regeneration even if unchanged")
@click.option("-o", "--output", "output_format", type=click.Choice(["text", "json"]), default="text", help="Output format")
@click.pass_context
def main(ctx, verbose, target, dry_run, force, output_format):
    """geni -- Python-powered infrastructure-as-code generator.

    When invoked without a subcommand, generates targets directly:

        geni -t prod          generate a single target

        geni                  generate all targets

        geni -t prod --dry-run

        geni -t prod -o json  structured JSON output
    """
    setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["config"] = GeniConfig.load()
    ctx.obj["verbose"] = verbose
    ctx.obj["output_format"] = output_format

    # If no subcommand was given, run generate as the default action
    if ctx.invoked_subcommand is None:
        try:
            _do_generate(ctx.obj["config"], target, dry_run, force, output_format)
        except GeniError as e:
            if output_format == "json":
                _output_result({"success": False, "error": str(e)}, "json")
            else:
                click.echo(f"Error: {e}", err=True)
            sys.exit(1)


@main.command(name="generate")
@click.option("-t", "--target", help="Target name to generate (without .yml extension)")
@click.option("--all", "generate_all", is_flag=True, help="Generate all targets")
@click.option("--dry-run", is_flag=True, help="Show what would be generated without writing")
@click.option("--force", is_flag=True, help="Force regeneration even if unchanged")
@click.option("-o", "--output", "output_format", type=click.Choice(["text", "json"]), default=None, help="Output format")
def generate(target, generate_all, dry_run, force, output_format):
    """Generate infrastructure artifacts from target YAML."""
    ctx = click.get_current_context()
    config = ctx.obj["config"]
    fmt = output_format or ctx.obj.get("output_format", "text")
    try:
        _do_generate(config, target, dry_run, force, fmt)
    except GeniError as e:
        if fmt == "json":
            _output_result({"success": False, "error": str(e)}, "json")
        else:
            click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# Short alias: geni g -t dev
main.add_command(generate, name="g")


@main.command()
@click.option("-t", "--target", help="Target name to validate")
@click.option("--all", "validate_all", is_flag=True, help="Validate all targets")
@click.option("-o", "--output", "output_format", type=click.Choice(["text", "json"]), default=None, help="Output format")
def validate(target, validate_all, output_format):
    """Validate target YAML files against the schema."""
    from geni.generator import GeniGenerator

    ctx = click.get_current_context()
    config = ctx.obj["config"]
    fmt = output_format or ctx.obj.get("output_format", "text")
    generator = GeniGenerator(config)

    targets = []
    if target:
        targets = [config.targets_dir / f"{target}.yml"]
    else:
        targets = sorted(config.targets_dir.glob("*.yml"))

    errors = 0
    results = []
    for t in targets:
        if not t.exists():
            errors += 1
            if fmt == "json":
                results.append({"target": t.stem, "valid": False, "error": f"Not found: {t}"})
            else:
                click.echo(f"[!] Not found: {t}", err=True)
            continue
        try:
            manifest = generator.validate_target(t)
            resource_count = len(manifest.spec.resources)
            if fmt == "json":
                results.append({
                    "target": t.stem,
                    "valid": True,
                    "resources": resource_count,
                })
            else:
                click.echo(f"[+] Valid: {t.stem}")
        except GeniError as e:
            errors += 1
            if fmt == "json":
                results.append({"target": t.stem, "valid": False, "error": str(e)})
            else:
                click.echo(f"[!] Invalid: {t.stem} -- {e}", err=True)

    if fmt == "json":
        _output_result({
            "success": errors == 0,
            "results": results,
        }, "json")

    if errors:
        sys.exit(1)


@main.command()
@click.option("-t", "--target", required=True, help="Target name to diff")
@click.option("-o", "--output", "output_format", type=click.Choice(["text", "json"]), default=None, help="Output format")
def diff(target, output_format):
    """Show what would change if a target were regenerated."""
    from geni.generator import GeniGenerator

    ctx = click.get_current_context()
    config = ctx.obj["config"]
    fmt = output_format or ctx.obj.get("output_format", "text")
    generator = GeniGenerator(config)

    target_path = config.targets_dir / f"{target}.yml"
    if not target_path.exists():
        if fmt == "json":
            _output_result({"success": False, "error": f"target file not found: {target_path}"}, "json")
        else:
            click.echo(f"Error: target file not found: {target_path}", err=True)
        sys.exit(1)

    try:
        diff_output = generator.diff_target(target_path)
        if fmt == "json":
            _output_result({
                "success": True,
                "target": target,
                "has_changes": bool(diff_output),
                "diff": diff_output if diff_output else None,
            }, "json")
        else:
            if diff_output:
                click.echo(diff_output)
            else:
                click.echo(f"No changes for target '{target}'")
    except GeniError as e:
        if fmt == "json":
            _output_result({"success": False, "error": str(e)}, "json")
        else:
            click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--dir", "project_dir", default=".", help="Directory to initialize")
@click.option("-o", "--output", "output_format", type=click.Choice(["text", "json"]), default=None, help="Output format")
def init(project_dir, output_format):
    """Initialize a new geni project with example files."""
    ctx = click.get_current_context()
    fmt = output_format or ctx.obj.get("output_format", "text")
    project = Path(project_dir)

    dirs = ["targets", "templates/terraform", "templates/kubernetes", "generated"]
    for d in dirs:
        (project / d).mkdir(parents=True, exist_ok=True)

    created_files = []

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
        created_files.append("targets/example.yml")

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
        created_files.append("templates/terraform/backend.tf")

    # Example .geni.yml
    config_file = project / ".geni.yml"
    if not config_file.exists():
        config_file.write_text("""templates_dir: templates
targets_dir: targets
generated_dir: generated
""")
        created_files.append(".geni.yml")

    if fmt == "json":
        _output_result({
            "success": True,
            "project_dir": str(project.resolve()),
            "created_files": created_files,
            "directories": dirs,
        }, "json")
    else:
        click.echo(f"[+] Initialized geni project in {project.resolve()}")
        click.echo("    - targets/example.yml (example target)")
        click.echo("    - templates/terraform/backend.tf (example template)")
        click.echo("    Run: geni generate -t example")
