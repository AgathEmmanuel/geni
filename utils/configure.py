import os
import re
import json
import yaml
import copy
import importlib.util
from pathlib import Path

def replace_key(obj, old_key, new_key):
    if isinstance(obj, dict):
        return {
            (new_key if k == old_key else k): replace_key(v, old_key, new_key)
            for k, v in obj.items()
        }
    elif isinstance(obj, list):
        return [replace_key(item, old_key, new_key) for item in obj]
    else:
        return obj

def deep_merge_dicts(a, b):
    result = dict(a)  # start with a copy of the first dict
    for key, value in b.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    return result