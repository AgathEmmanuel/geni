from __future__ import annotations
import re
import importlib.util
import inspect
import json
import yaml
import os
from pathlib import Path
from typing import Any

import logging

from geni.template import Template, GeneratedFile, RenderContext, TerraformJSON, TerraformHCL, KubernetesManifest
from geni.errors import TemplateError

logger = logging.getLogger(__name__)


class TemplateEngine:
    """Loads and executes templates, returning GeneratedFile instances."""

    def __init__(self, templates_dir: Path):
        self.templates_dir = templates_dir

    def load_and_render(
        self, resource_name: str, template_path: str, context: RenderContext
    ) -> list[GeneratedFile]:
        """Load a template by path and render it, returning a list of GeneratedFile."""
        abs_path = (self.templates_dir / template_path).resolve()

        if template_path.endswith(".py"):
            result = self._render_python_template(resource_name, abs_path, context)
        else:
            result = self._render_static_template(resource_name, abs_path, context)

        # Always return a list
        if isinstance(result, list):
            return result
        return [result]

    def _render_python_template(
        self, resource_name: str, abs_path: Path, context: RenderContext
    ) -> list[GeneratedFile]:
        """Load and execute a Python template module."""
        # SECURITY: Validate the resolved path is within templates_dir
        resolved_templates = self.templates_dir.resolve()
        resolved_path = abs_path.resolve()
        if not str(resolved_path).startswith(str(resolved_templates) + os.sep) and resolved_path != resolved_templates:
            raise TemplateError(
                f"Template path {abs_path} is outside templates directory {self.templates_dir}"
            )

        if not resolved_path.exists():
            # Check if a similar file exists to give a helpful hint
            parent = resolved_path.parent
            hint = ""
            if parent.exists():
                similar = [f.name for f in parent.iterdir() if f.suffix in (".py", ".tf", ".yml", ".json")]
                if similar:
                    hint = f" Available templates in {parent.name}/: {', '.join(sorted(similar))}"
            raise TemplateError(f"Template file not found: {abs_path}.{hint}")

        # Load the module dynamically
        module_name = f"geni_template_{resource_name}"
        spec = importlib.util.spec_from_file_location(module_name, str(resolved_path))
        if spec is None or spec.loader is None:
            raise TemplateError(f"Could not load template module: {abs_path}")

        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            raise TemplateError(f"Error loading template {abs_path}: {e}") from e

        # Find the first class that is a subclass of Template
        template_cls = None
        for attr_name, attr_value in module.__dict__.items():
            if (
                isinstance(attr_value, type)
                and issubclass(attr_value, Template)
                and attr_value is not Template
            ):
                template_cls = attr_value
                break

        if template_cls is not None:
            instance = template_cls(resource_name)
            result = instance.render(context)
        elif hasattr(module, "render") and callable(module.render):
            # Fallback: module-level render(context) function
            result = module.render(context)
        else:
            raise TemplateError(
                f"Template {abs_path} has no Template subclass and no render() function"
            )

        if isinstance(result, list):
            return result
        return [result]

    def _render_static_template(
        self, resource_name: str, abs_path: Path, context: RenderContext
    ) -> list[GeneratedFile]:
        """Render a static template file with variable substitution."""
        if not abs_path.exists():
            parent = abs_path.parent
            hint = ""
            if parent.exists():
                similar = [f.name for f in parent.iterdir() if f.is_file()]
                if similar:
                    hint = f" Available files in {parent.name}/: {', '.join(sorted(similar))}"
            raise TemplateError(f"Template file not found: {abs_path}.{hint}")

        raw_content = abs_path.read_text(encoding="utf-8")
        rendered = self._substitute(raw_content, context)

        filename = abs_path.name
        suffixes = "".join(abs_path.suffixes)

        if suffixes.endswith(".tf.json"):
            try:
                parsed = json.loads(rendered)
            except json.JSONDecodeError as e:
                raise TemplateError(f"Invalid JSON in template {abs_path}: {e}") from e
            return [TerraformJSON(resource_name + ".tf.json", parsed)]

        elif filename.endswith(".tf"):
            return [TerraformHCL(resource_name + ".tf", rendered)]

        elif filename.endswith(".yml") or filename.endswith(".yaml"):
            if "\n---\n" in rendered:
                docs = list(yaml.safe_load_all(rendered))
                return [KubernetesManifest(resource_name + ".yml", docs)]
            else:
                doc = yaml.safe_load(rendered)
                return [KubernetesManifest(resource_name + ".yml", doc)]

        elif filename.endswith(".json"):
            try:
                parsed = json.loads(rendered)
            except json.JSONDecodeError as e:
                raise TemplateError(f"Invalid JSON in template {abs_path}: {e}") from e
            return [GeneratedFile(resource_name + ".json", parsed, "json")]

        else:
            # Treat as raw text file, preserve original extension
            ext = abs_path.suffix.lstrip(".") if abs_path.suffix else "txt"
            return [GeneratedFile(resource_name + abs_path.suffix, rendered, ext)]

    def _substitute(self, content: str, context: RenderContext) -> str:
        """Replace ${{ param_name }} and ${{ data.xxx }} placeholders."""
        pattern = re.compile(r"\$\{\{\s*(.+?)\s*\}\}")

        def _replace(match: re.Match) -> str:
            key = match.group(1)
            value = None

            if key.startswith("data."):
                data_key = key[len("data."):]
                value = self._lookup(context.data, data_key)
            else:
                value = self._lookup(context.params, key)

            if value is None:
                # Not found — leave placeholder as-is
                return match.group(0)

            if isinstance(value, (dict, list)):
                return json.dumps(value)
            return str(value)

        result = pattern.sub(_replace, content)

        # Warn about unresolved placeholders
        unresolved = pattern.findall(result)
        if unresolved:
            logger.warning(
                f"Unresolved placeholders in template: {', '.join('${{{{ {} }}}}'.format(k) for k in unresolved)}. "
                f"Check that these keys exist in params or data."
            )

        return result

    @staticmethod
    def _lookup(data: dict[str, Any], dotted_key: str) -> Any | None:
        """Look up a dotted key path in a nested dict."""
        keys = dotted_key.split(".")
        current = data
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None
        return current
