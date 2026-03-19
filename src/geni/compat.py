from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml


def is_legacy_format(raw: dict[str, Any]) -> bool:
    """Return ``True`` if the raw dict lacks an ``apiVersion`` key,
    indicating it uses the legacy target format."""
    return "apiVersion" not in raw


def upgrade_legacy_target(raw: dict[str, Any], filename: str) -> dict[str, Any]:
    """Transform a legacy target dict into the v1alpha1 envelope format.

    Mapping rules:
    - ``data``       -> ``spec.data``
    - ``compiled``   -> ``spec.output``
    - ``resources``  -> ``spec.resources`` (with key renames)
    - ``parameter``  -> ``params``
    - ``component``  -> ``template``
    - ``value`` (in chart resources) -> ``values``
    - ``metadata.name`` is derived from the file stem of *filename*.
    """
    print(
        f"WARNING: '{filename}' uses the legacy target format. "
        "Please migrate to apiVersion geni.io/v1alpha1. "
        "Run migrate_target_file() to auto-convert.",
        file=sys.stderr,
    )

    name = Path(filename).stem

    # --- resources conversion -------------------------------------------
    old_resources: dict[str, Any] = raw.get("resources", {})
    new_resources: dict[str, Any] = {}

    for res_name, res_def in old_resources.items():
        if not isinstance(res_def, dict):
            new_resources[res_name] = res_def
            continue

        new_def: dict[str, Any] = {}

        # component -> template
        if "component" in res_def:
            new_def["template"] = res_def["component"]
        elif "template" in res_def:
            new_def["template"] = res_def["template"]

        # chart — legacy uses plain string, convert to dict with path
        if "chart" in res_def:
            chart_val = res_def["chart"]
            if isinstance(chart_val, str):
                new_def["chart"] = {"path": chart_val}
            else:
                new_def["chart"] = chart_val

        # generator passthrough
        if "generator" in res_def:
            new_def["generator"] = res_def["generator"]

        # value -> values
        if "value" in res_def:
            new_def["values"] = res_def["value"]
        elif "values" in res_def:
            new_def["values"] = res_def["values"]

        # parameter -> params
        if "parameter" in res_def:
            new_def["params"] = res_def["parameter"]
        elif "params" in res_def:
            new_def["params"] = res_def["params"]

        new_resources[res_name] = new_def

    return {
        "apiVersion": "geni.io/v1alpha1",
        "kind": "Target",
        "metadata": {
            "name": name,
            "labels": {},
        },
        "spec": {
            "data": raw.get("data", {}),
            "output": raw.get("compiled", ""),
            "resources": new_resources,
        },
    }


def migrate_target_file(path: Path) -> None:
    """Read a legacy target file, convert it to v1alpha1, and write it back."""
    text = path.read_text(encoding="utf-8")
    raw = yaml.safe_load(text)

    if not isinstance(raw, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")

    if not is_legacy_format(raw):
        print(f"'{path}' is already in the new format; skipping.", file=sys.stderr)
        return

    upgraded = upgrade_legacy_target(raw, path.name)
    path.write_text(
        yaml.dump(upgraded, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    print(f"Migrated '{path}' to geni.io/v1alpha1 format.", file=sys.stderr)
