from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass, field

import yaml


@dataclass
class GeniConfig:
    templates_dir: Path = field(default_factory=lambda: Path("templates"))
    targets_dir: Path = field(default_factory=lambda: Path("targets"))
    generated_dir: Path = field(default_factory=lambda: Path("generated"))

    @classmethod
    def load(cls, project_root: Path = Path(".")) -> GeniConfig:
        """Load config from .geni.yml if it exists, otherwise use defaults."""
        config_path = project_root / ".geni.yml"
        if config_path.exists():
            with open(config_path) as f:
                raw = yaml.safe_load(f) or {}
            return cls(
                templates_dir=Path(raw.get("templates_dir", "templates")),
                targets_dir=Path(raw.get("targets_dir", "targets")),
                generated_dir=Path(raw.get("generated_dir", "generated")),
            )
        return cls()
