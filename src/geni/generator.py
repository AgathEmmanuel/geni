from __future__ import annotations
import difflib
import json
import logging
import tempfile
import yaml
from pathlib import Path
from typing import Any

from geni.schema import TargetManifest, load_target, resolve_refs, ResourceDef, ChartSource
from geni.engine import TemplateEngine
from geni.template import RenderContext, GeneratedFile
from geni.writers import FileWriter
from geni.integrations.helm import render_helm_chart, HelmChartResolver
from geni.integrations.hcl import convert_hcl_to_json
from geni.state import GeniLockFile, AtomicGenerator, compute_hash, hash_file
from geni.config import GeniConfig
from geni.errors import GeniError, GenerationError

logger = logging.getLogger(__name__)


class GeniGenerator:
    """Main generation orchestrator for geni targets."""

    def __init__(self, config: GeniConfig):
        self.config = config
        self.engine = TemplateEngine(config.templates_dir)
        self.helm_resolver = HelmChartResolver()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_target(
        self,
        target_path: Path,
        dry_run: bool = False,
        force: bool = False,
    ) -> list[Path]:
        """Generate artifacts from a single target file and return the list of written paths."""
        manifest = self._load_and_validate(target_path)
        target_name = manifest.metadata.name
        data = manifest.spec.data
        output_dir = Path(manifest.spec.output)

        # Resolve ${{ data.xxx }} references in all resource params
        resolved_resources: dict[str, ResourceDef] = {}
        for res_name, res_def in manifest.spec.resources.items():
            resolved_params = resolve_refs(res_def.params, data)
            resolved_resources[res_name] = res_def.model_copy(
                update={"params": resolved_params}
            )

        # Check lock file for incremental generation
        lock_path = output_dir / ".geni-lock.json"
        lock_file = GeniLockFile(lock_path)
        input_hash = compute_hash(target_path)

        if not force and lock_file.get_input_hash(target_name) == input_hash:
            logger.info(
                f"Target '{target_name}' is up to date (hash {input_hash[:12]}...); "
                f"skipping. Use --force to regenerate."
            )
            return []

        # Generate
        all_written: list[Path] = []

        if dry_run:
            staging_dir = Path(tempfile.mkdtemp(prefix="geni-dry-run-"))
            all_written = self._do_generate(
                resolved_resources, data, staging_dir, target_name
            )
            logger.info(f"Dry run: would write {len(all_written)} files to {output_dir}")
            return all_written

        with AtomicGenerator(output_dir) as ag:
            all_written = self._do_generate(
                resolved_resources, data, ag.staging_path, target_name
            )

        # Update lock file after successful generation
        output_hashes = {}
        for p in all_written:
            if p.exists():
                try:
                    rel = str(p.relative_to(output_dir))
                except ValueError:
                    rel = p.name
                output_hashes[rel] = hash_file(p)

        # Re-compute hashes from actual output dir after swap
        if output_dir.exists():
            output_hashes = {}
            for f in output_dir.rglob("*"):
                if f.is_file() and not f.name.startswith(".geni-"):
                    rel = str(f.relative_to(output_dir))
                    output_hashes[rel] = hash_file(f)

        lock_file.update(target_name, input_hash, output_hashes)
        lock_file.save()

        logger.info(
            f"Generated target '{target_name}': {len(all_written)} files -> {output_dir}"
        )
        return all_written

    def generate_all(
        self,
        dry_run: bool = False,
        force: bool = False,
    ) -> dict[str, list[Path]]:
        """Generate artifacts for all targets in the targets directory."""
        results: dict[str, list[Path]] = {}
        targets_dir = self.config.targets_dir

        if not targets_dir.exists():
            logger.warning(f"Targets directory not found: {targets_dir}")
            return results

        for target_file in sorted(targets_dir.glob("*.yml")):
            target_name = target_file.stem
            try:
                paths = self.generate_target(target_file, dry_run=dry_run, force=force)
                results[target_name] = paths
            except GeniError as e:
                logger.error(f"Failed to generate target '{target_name}': {e}")
                results[target_name] = []

        return results

    def validate_target(self, target_path: Path) -> TargetManifest:
        """Load and validate a target, returning the manifest or raising."""
        return self._load_and_validate(target_path)

    def diff_target(self, target_path: Path) -> str:
        """Generate to a temp dir and diff against current output."""
        manifest = self._load_and_validate(target_path)
        output_dir = Path(manifest.spec.output)
        data = manifest.spec.data

        resolved_resources: dict[str, ResourceDef] = {}
        for res_name, res_def in manifest.spec.resources.items():
            resolved_params = resolve_refs(res_def.params, data)
            resolved_resources[res_name] = res_def.model_copy(
                update={"params": resolved_params}
            )

        staging_dir = Path(tempfile.mkdtemp(prefix="geni-diff-"))
        self._do_generate(resolved_resources, data, staging_dir, manifest.metadata.name)

        diff_lines: list[str] = []

        # Compare files
        all_files: set[str] = set()

        if output_dir.exists():
            for f in output_dir.rglob("*"):
                if f.is_file() and not f.name.startswith(".geni-"):
                    all_files.add(str(f.relative_to(output_dir)))

        for f in staging_dir.rglob("*"):
            if f.is_file():
                all_files.add(str(f.relative_to(staging_dir)))

        for rel in sorted(all_files):
            old_path = output_dir / rel
            new_path = staging_dir / rel

            old_lines = (
                old_path.read_text(encoding="utf-8").splitlines(keepends=True)
                if old_path.exists()
                else []
            )
            new_lines = (
                new_path.read_text(encoding="utf-8").splitlines(keepends=True)
                if new_path.exists()
                else []
            )

            diff = difflib.unified_diff(
                old_lines, new_lines,
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
            )
            diff_lines.extend(diff)

        return "".join(diff_lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_and_validate(self, target_path: Path) -> TargetManifest:
        """Load and validate a target file."""
        raw = yaml.safe_load(target_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise GenerationError(
                "Target file must be a YAML mapping", path=str(target_path)
            )

        return TargetManifest.model_validate(raw)

    def _do_generate(
        self,
        resources: dict[str, ResourceDef],
        data: dict[str, Any],
        staging_dir: Path,
        target_name: str,
    ) -> list[Path]:
        """Generate all resources into the staging directory."""
        writer = FileWriter(staging_dir)
        generated_resources: dict[str, Any] = {}
        all_written: list[Path] = []

        for res_name, res_def in resources.items():
            if res_def.template is not None:
                written = self._generate_template_resource(
                    res_name, res_def, data, generated_resources, staging_dir, writer
                )
                all_written.extend(written)

            elif res_def.chart is not None:
                written = self._generate_chart_resource(
                    res_name, res_def, data, staging_dir
                )
                all_written.extend(written)

            else:
                logger.warning(
                    f"Resource '{res_name}' has no template or chart; skipping"
                )

        return all_written

    def _generate_template_resource(
        self,
        res_name: str,
        res_def: ResourceDef,
        data: dict[str, Any],
        generated_resources: dict[str, Any],
        staging_dir: Path,
        writer: FileWriter,
    ) -> list[Path]:
        """Generate a template-based resource."""
        template_path = res_def.template
        assert template_path is not None

        context = RenderContext(
            params=res_def.params,
            data=data,
            resources=generated_resources,
            templates_dir=self.config.templates_dir,
            output_dir=staging_dir,
            _helm_resolver=self.helm_resolver,
        )

        # If it's a .tf file (raw HCL, not .tf.json and not .py), try converting
        # to JSON via hcl2json. If that fails, render as plain text.
        if template_path.endswith(".tf") and not template_path.endswith(".tf.json"):
            hcl_abs = (self.config.templates_dir / template_path).resolve()
            if hcl_abs.exists():
                try:
                    json_path = convert_hcl_to_json(hcl_abs)
                    rel_json = json_path.relative_to(self.config.templates_dir.resolve())
                    template_path = str(rel_json)
                except GenerationError:
                    logger.debug(
                        f"hcl2json conversion failed for {template_path}, "
                        "rendering as static HCL template"
                    )

        generated = self.engine.load_and_render(res_name, template_path, context)

        written_paths = writer.write_all(generated)

        # Store in generated_resources for cross-resource references
        for gf in generated:
            generated_resources[res_name] = gf.content

        return written_paths

    def _generate_chart_resource(
        self,
        res_name: str,
        res_def: ResourceDef,
        data: dict[str, Any],
        staging_dir: Path,
    ) -> list[Path]:
        """Generate a Helm chart resource."""
        chart_source = res_def.chart
        if chart_source is None:
            return []

        # Ensure chart_source is a ChartSource object
        if isinstance(chart_source, dict):
            chart_source = ChartSource.model_validate(chart_source)

        # Resolve chart path
        if chart_source.is_local:
            chart_path = Path(chart_source.path)
        else:
            chart_path = self.helm_resolver.resolve(
                chart_source.repo, chart_source.name, chart_source.version
            )

        # Load and substitute values
        values: dict[str, Any] = {}
        if res_def.values is not None:
            values_path = Path(res_def.values)
            if values_path.exists():
                raw_values = values_path.read_text(encoding="utf-8")
                # Substitute ${{ data.xxx }} and ${{ param }} placeholders
                context = RenderContext(
                    params=res_def.params,
                    data=data,
                    resources={},
                    templates_dir=self.config.templates_dir,
                    output_dir=staging_dir,
                    _helm_resolver=self.helm_resolver,
                )
                rendered_values = self.engine._substitute(raw_values, context)
                values = yaml.safe_load(rendered_values) or {}

        # Merge any inline params into values
        if res_def.params:
            values.update(res_def.params)

        namespace = data.get("namespace", "default")
        return render_helm_chart(
            chart_path=chart_path,
            release_name=res_name,
            values=values,
            output_dir=staging_dir,
            namespace=namespace,
        )
