from __future__ import annotations
import subprocess
import tempfile
import os
import yaml
import logging
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from geni.errors import HelmError

logger = logging.getLogger(__name__)


def render_helm_chart(
    chart_path: Path,
    release_name: str,
    values: dict[str, Any],
    output_dir: Path,
    namespace: str = "default",
) -> list[Path]:
    """Render a Helm chart using helm template.

    Returns list of generated file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yml") as tf:
        yaml.dump(values, tf)
        tf.flush()
        values_path = tf.name

    try:
        cmd = [
            "helm", "template", release_name,
            str(chart_path),
            "--namespace", namespace,
            "--output-dir", str(output_dir),
            "-f", values_path,
        ]
        logger.info(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode != 0:
            raise HelmError(f"helm template failed: {result.stderr}")

        logger.info(f"Rendered Helm chart '{release_name}' to {output_dir}")

        # Collect generated files
        generated = []
        for root, dirs, files in os.walk(output_dir):
            for f in files:
                generated.append(Path(root) / f)
        return generated
    except FileNotFoundError:
        raise HelmError(
            "helm not found. Install Helm: https://helm.sh/docs/intro/install/"
        )
    except subprocess.TimeoutExpired:
        raise HelmError(f"helm template timed out for chart {chart_path}")
    finally:
        os.unlink(values_path)


class HelmChartResolver:
    """Resolves and caches Helm charts from registries."""

    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir or Path.home() / ".cache" / "geni" / "charts"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def resolve(self, repo: str, name: str, version: str) -> Path:
        """Pull a chart from a registry and return its local path."""
        repo_hash = hashlib.sha256(repo.encode()).hexdigest()[:12]
        chart_dir = self.cache_dir / repo_hash / name / version

        if chart_dir.exists() and any(chart_dir.iterdir()):
            logger.debug(f"Using cached chart {name}@{version}")
            return chart_dir

        chart_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Pulling chart {name}@{version} from {repo}")

        try:
            # Add repo temporarily
            repo_name = f"geni-{repo_hash}"
            subprocess.run(
                ["helm", "repo", "add", repo_name, repo, "--force-update"],
                capture_output=True, text=True, check=True, timeout=30,
            )
            subprocess.run(
                ["helm", "repo", "update", repo_name],
                capture_output=True, text=True, check=True, timeout=30,
            )

            # Pull chart
            result = subprocess.run(
                [
                    "helm", "pull", f"{repo_name}/{name}",
                    "--version", version,
                    "--untar", "--untardir", str(chart_dir.parent),
                ],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                raise HelmError(f"helm pull failed: {result.stderr}")

            # helm pull untars to chart_dir.parent/name, rename to versioned dir
            pulled = chart_dir.parent / name
            if pulled.exists() and pulled != chart_dir:
                if chart_dir.exists():
                    shutil.rmtree(chart_dir)
                pulled.rename(chart_dir)

            logger.info(f"Cached chart {name}@{version} at {chart_dir}")
            return chart_dir

        except FileNotFoundError:
            raise HelmError(
                "helm not found. Install Helm: https://helm.sh/docs/intro/install/"
            )
        except subprocess.CalledProcessError as e:
            raise HelmError(f"Helm command failed: {e.stderr}")
        except subprocess.TimeoutExpired:
            raise HelmError(f"Helm operation timed out for {name}@{version}")

    def write_lock(self, lock_path: Path, entries: dict[str, dict]):
        """Write chart lock file."""
        with open(lock_path, "w") as f:
            json.dump({"version": 1, "charts": entries}, f, indent=2)

    def read_lock(self, lock_path: Path) -> dict[str, dict]:
        """Read chart lock file."""
        if not lock_path.exists():
            return {}
        with open(lock_path) as f:
            data = json.load(f)
        return data.get("charts", {})
