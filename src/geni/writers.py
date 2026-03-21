from __future__ import annotations
import json
import yaml
import os
from pathlib import Path
from typing import Any

from geni.template import GeneratedFile


class FileWriter:
    """Serializes GeneratedFile instances to disk."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write(self, generated: GeneratedFile) -> Path:
        """Write a single GeneratedFile to disk and return its path."""
        full_path = self.output_dir / generated.filename
        full_path.parent.mkdir(parents=True, exist_ok=True)

        if generated.file_type in ("tf.json", "json"):
            with open(full_path, "w", encoding="utf-8") as f:
                json.dump(generated.content, f, indent=2)
                f.write("\n")
        elif generated.file_type == "yaml":
            with open(full_path, "w", encoding="utf-8") as f:
                if isinstance(generated.content, list):
                    yaml.dump_all(
                        generated.content, f,
                        default_flow_style=False,
                        explicit_start=True,
                    )
                else:
                    yaml.safe_dump(
                        generated.content, f,
                        default_flow_style=False,
                    )
        else:
            # "tf" or any other type — write content as a string directly
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(str(generated.content))

        return full_path

    def write_all(self, files: list[GeneratedFile]) -> list[Path]:
        """Write multiple GeneratedFile instances and return their paths."""
        return [self.write(gf) for gf in files]
