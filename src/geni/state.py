from __future__ import annotations
import json
import hashlib
import shutil
import logging
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class LockEntry:
    input_hash: str
    outputs: dict[str, str]  # filename -> sha256


class GeniLockFile:
    """Manages .geni-lock.json for tracking generation state."""

    def __init__(self, lock_path: Path):
        self.lock_path = lock_path
        self._data: dict = {"version": 1, "generated_at": None, "targets": {}}
        if lock_path.exists():
            with open(lock_path) as f:
                self._data = json.load(f)

    def get_input_hash(self, target_name: str) -> str | None:
        entry = self._data.get("targets", {}).get(target_name)
        return entry.get("input_hash") if entry else None

    def update(self, target_name: str, input_hash: str, outputs: dict[str, str]):
        self._data["generated_at"] = datetime.now(timezone.utc).isoformat()
        self._data.setdefault("targets", {})[target_name] = {
            "input_hash": input_hash,
            "outputs": outputs,
        }

    def save(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.lock_path, "w") as f:
            json.dump(self._data, f, indent=2)

    def get_tracked_files(self, target_name: str) -> set[str]:
        entry = self._data.get("targets", {}).get(target_name, {})
        return set(entry.get("outputs", {}).keys())


def compute_hash(*paths: Path) -> str:
    """Compute combined SHA256 hash of multiple files."""
    h = hashlib.sha256()
    for path in sorted(paths):
        if path.exists():
            h.update(path.read_bytes())
    return h.hexdigest()


def hash_file(path: Path) -> str:
    """SHA256 hash of a single file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AtomicGenerator:
    """Generates to a staging directory and atomically swaps on success."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.staging_dir = output_dir.parent / f".geni-staging-{output_dir.name}"
        self._files_written: list[Path] = []

    def __enter__(self):
        if self.staging_dir.exists():
            shutil.rmtree(self.staging_dir)
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Generation failed -- clean up staging, keep original
            logger.error("Generation failed, cleaning up staging dir")
            if self.staging_dir.exists():
                shutil.rmtree(self.staging_dir)
            return False

        # Success -- swap staging into place
        self._swap()
        return False

    @property
    def staging_path(self) -> Path:
        return self.staging_dir

    def _swap(self):
        """Atomically replace output_dir with staging_dir."""
        backup = None
        if self.output_dir.exists():
            # Preserve .terraform directories
            terraform_dirs = []
            for item in self.output_dir.rglob(".terraform*"):
                terraform_dirs.append(item)

            backup = self.output_dir.parent / f".geni-backup-{self.output_dir.name}"
            if backup.exists():
                shutil.rmtree(backup)
            self.output_dir.rename(backup)

        self.staging_dir.rename(self.output_dir)

        # Restore .terraform dirs from backup
        if backup and backup.exists():
            for item in backup.rglob(".terraform*"):
                rel = item.relative_to(backup)
                dest = self.output_dir / rel
                if not dest.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if item.is_dir():
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)
            shutil.rmtree(backup)

        logger.info(f"Generated output written to {self.output_dir}")

    def get_output_hashes(self) -> dict[str, str]:
        """Get SHA256 hashes of all files in output_dir."""
        hashes = {}
        if self.output_dir.exists():
            for f in self.output_dir.rglob("*"):
                if f.is_file() and not f.name.startswith(".geni-"):
                    rel = str(f.relative_to(self.output_dir))
                    hashes[rel] = hash_file(f)
        return hashes
