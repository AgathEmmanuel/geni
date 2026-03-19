from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for test output."""
    d = Path(tempfile.mkdtemp(prefix="geni-test-"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def fixture_dir():
    """Return the path to the test fixtures directory."""
    return FIXTURES_DIR
