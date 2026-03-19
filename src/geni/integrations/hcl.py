from __future__ import annotations
import subprocess
import logging
from pathlib import Path

from geni.errors import CompilationError

logger = logging.getLogger(__name__)


def convert_hcl_to_json(hcl_path: Path, output_dir: Path | None = None) -> Path:
    """Convert an HCL file to JSON using hcl2json.

    Returns the path to the generated .tf.json file.
    """
    if not hcl_path.exists():
        raise CompilationError(f"HCL file not found: {hcl_path}", path=str(hcl_path))

    if output_dir is None:
        output_dir = hcl_path.parent

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / (hcl_path.stem + ".tf.json")

    # Skip if output is newer than input
    if json_path.exists() and json_path.stat().st_mtime > hcl_path.stat().st_mtime:
        logger.debug(f"Skipping conversion, {json_path} is up to date")
        return json_path

    logger.info(f"Converting {hcl_path} -> {json_path}")

    try:
        with open(hcl_path, "r") as input_file, open(json_path, "w") as output_file:
            result = subprocess.run(
                ["hcl2json"],
                stdin=input_file,
                stdout=output_file,
                stderr=subprocess.PIPE,
                timeout=10,
            )
        if result.returncode != 0:
            # Clean up empty/corrupt output file
            if json_path.exists():
                json_path.unlink()
            stderr = result.stderr.decode().strip() if result.stderr else "unknown error"
            raise CompilationError(
                f"hcl2json failed: {stderr}", path=str(hcl_path)
            )
        return json_path
    except FileNotFoundError:
        raise CompilationError(
            "hcl2json not found. Install it: https://github.com/tmccombs/hcl2json",
            path=str(hcl_path),
        )
    except subprocess.TimeoutExpired:
        raise CompilationError(
            f"hcl2json timed out converting {hcl_path}", path=str(hcl_path)
        )
