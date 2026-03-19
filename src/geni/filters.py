from __future__ import annotations
import json
import yaml
import base64
import hashlib
from typing import Any

def to_json(obj: Any, indent: int = 2) -> str:
    return json.dumps(obj, indent=indent)

def to_yaml(obj: Any) -> str:
    return yaml.safe_dump(obj, default_flow_style=False)

def b64encode(s: str) -> str:
    return base64.b64encode(s.encode()).decode()

def b64decode(s: str) -> str:
    return base64.b64decode(s.encode()).decode()

def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()

def deep_merge(a: dict, b: dict) -> dict:
    """Deep merge dict b into dict a. b values win on conflict."""
    result = dict(a)
    for key, value in b.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result

def sanitize_terraform_name(name: str) -> str:
    """Convert a string to a valid Terraform resource name."""
    return name.replace(".", "_").replace("-", "_").strip("_")
