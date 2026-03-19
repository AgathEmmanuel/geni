from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional, Union

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from geni.errors import SchemaValidationError


class Metadata(BaseModel):
    name: str
    labels: dict[str, str] = {}


class LocalChart(BaseModel):
    path: str


class RegistryChart(BaseModel):
    repo: str
    name: str
    version: str


class ChartSource(BaseModel):
    """Union of LocalChart and RegistryChart, discriminated by field presence."""

    root: Union[LocalChart, RegistryChart]

    @model_validator(mode="before")
    @classmethod
    def _parse_chart(cls, values: Any) -> Any:
        if isinstance(values, dict):
            # Called directly with the chart dict, not wrapped in {"root": ...}
            if "root" not in values:
                if "path" in values:
                    return {"root": LocalChart(**values)}
                elif "repo" in values:
                    return {"root": RegistryChart(**values)}
                else:
                    raise SchemaValidationError(
                        "Chart must contain either 'path' (local) or 'repo' (registry) field"
                    )
        return values

    def __getattr__(self, item: str) -> Any:
        # Delegate attribute access to the inner model for convenience
        try:
            return getattr(self.root, item)
        except AttributeError:
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{item}'"
            )

    @property
    def is_local(self) -> bool:
        return isinstance(self.root, LocalChart)


class ResourceDef(BaseModel):
    template: Optional[str] = None
    chart: Optional[Union[ChartSource, dict[str, Any]]] = None
    values: Optional[str] = None
    generator: Optional[str] = None
    params: dict[str, Any] = {}

    @model_validator(mode="before")
    @classmethod
    def _parse_chart_field(cls, values: Any) -> Any:
        if isinstance(values, dict) and "chart" in values and values["chart"] is not None:
            chart_val = values["chart"]
            if isinstance(chart_val, dict):
                values = {**values, "chart": ChartSource.model_validate(chart_val)}
        return values

    @model_validator(mode="after")
    def _check_exactly_one_source(self) -> ResourceDef:
        sources = [
            self.template is not None,
            self.chart is not None,
            self.generator is not None,
        ]
        count = sum(sources)
        if count == 0:
            raise SchemaValidationError(
                "Resource must specify exactly one of 'template', 'chart', or 'generator'; none were set"
            )
        if count > 1:
            raise SchemaValidationError(
                "Resource must specify exactly one of 'template', 'chart', or 'generator'; multiple were set"
            )
        return self


class Spec(BaseModel):
    data: dict[str, Any] = {}
    output: str
    resources: dict[str, ResourceDef]


class TargetManifest(BaseModel):
    model_config = ConfigDict(extra="allow")

    apiVersion: str
    kind: str
    metadata: Metadata
    spec: Spec

    @field_validator("apiVersion")
    @classmethod
    def _check_api_version(cls, v: str) -> str:
        if v != "geni.io/v1alpha1":
            raise SchemaValidationError(
                f"Unsupported apiVersion '{v}'; expected 'geni.io/v1alpha1'"
            )
        return v

    @field_validator("kind")
    @classmethod
    def _check_kind(cls, v: str) -> str:
        if v != "Target":
            raise SchemaValidationError(
                f"Unsupported kind '{v}'; expected 'Target'"
            )
        return v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REF_PATTERN = re.compile(r"\$\{\{\s*data\.(\w+)\s*\}\}")


def resolve_refs(value: Any, data: dict[str, Any]) -> Any:
    """Recursively walk a dict/list/string and replace ``${{ data.xxx }}``
    patterns with the corresponding value from *data*."""
    if isinstance(value, str):
        # If the whole string is a single reference, return the raw value
        # (preserving type).  Otherwise do string substitution.
        match = _REF_PATTERN.fullmatch(value)
        if match:
            key = match.group(1)
            return data.get(key, value)
        return _REF_PATTERN.sub(
            lambda m: str(data.get(m.group(1), m.group(0))), value
        )
    if isinstance(value, dict):
        return {k: resolve_refs(v, data) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_refs(item, data) for item in value]
    return value


def load_target(path: Path) -> TargetManifest:
    """Read a YAML target file, validate it, and return a ``TargetManifest``."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SchemaValidationError(
            f"Failed to read target YAML: {exc}", path=str(path)
        ) from exc

    if not isinstance(raw, dict):
        raise SchemaValidationError(
            "Target YAML must be a mapping at the top level", path=str(path)
        )

    try:
        return TargetManifest.model_validate(raw)
    except SchemaValidationError:
        raise
    except Exception as exc:
        raise SchemaValidationError(
            f"Target validation failed: {exc}", path=str(path)
        ) from exc
