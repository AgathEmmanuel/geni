from __future__ import annotations

import json
from pathlib import Path

import pytest

from geni.state import GeniLockFile, compute_hash, hash_file, AtomicCompiler


class TestGeniLockFile:
    def test_new_lock_file(self, tmp_dir):
        lock_path = tmp_dir / ".geni-lock.json"
        lock = GeniLockFile(lock_path)
        assert lock.get_input_hash("test") is None

    def test_update_and_save(self, tmp_dir):
        lock_path = tmp_dir / ".geni-lock.json"
        lock = GeniLockFile(lock_path)
        lock.update("test-target", "abc123", {"file.tf": "def456"})
        lock.save()

        # Reload
        lock2 = GeniLockFile(lock_path)
        assert lock2.get_input_hash("test-target") == "abc123"
        assert lock2.get_tracked_files("test-target") == {"file.tf"}

    def test_multiple_targets(self, tmp_dir):
        lock_path = tmp_dir / ".geni-lock.json"
        lock = GeniLockFile(lock_path)
        lock.update("target1", "hash1", {"a.tf": "h1"})
        lock.update("target2", "hash2", {"b.tf": "h2"})
        lock.save()

        lock2 = GeniLockFile(lock_path)
        assert lock2.get_input_hash("target1") == "hash1"
        assert lock2.get_input_hash("target2") == "hash2"


class TestComputeHash:
    def test_single_file(self, tmp_dir):
        f = tmp_dir / "test.txt"
        f.write_text("hello")
        h = compute_hash(f)
        assert len(h) == 64  # SHA256 hex

    def test_deterministic(self, tmp_dir):
        f = tmp_dir / "test.txt"
        f.write_text("hello")
        assert compute_hash(f) == compute_hash(f)

    def test_different_content(self, tmp_dir):
        f1 = tmp_dir / "a.txt"
        f2 = tmp_dir / "b.txt"
        f1.write_text("hello")
        f2.write_text("world")
        assert compute_hash(f1) != compute_hash(f2)


class TestAtomicCompiler:
    def test_successful_swap(self, tmp_dir):
        output = tmp_dir / "output"

        with AtomicCompiler(output) as ac:
            (ac.staging_path / "test.tf").write_text("resource {}")

        assert output.exists()
        assert (output / "test.tf").exists()
        assert (output / "test.tf").read_text() == "resource {}"

    def test_failed_compilation_preserves_original(self, tmp_dir):
        output = tmp_dir / "output"
        output.mkdir()
        (output / "original.tf").write_text("original content")

        with pytest.raises(ValueError):
            with AtomicCompiler(output) as ac:
                (ac.staging_path / "new.tf").write_text("new content")
                raise ValueError("compilation failed")

        # Original should be preserved
        assert (output / "original.tf").exists()
        assert (output / "original.tf").read_text() == "original content"
        assert not (output / "new.tf").exists()

    def test_preserves_terraform_dirs(self, tmp_dir):
        output = tmp_dir / "output"
        output.mkdir()
        tf_dir = output / ".terraform"
        tf_dir.mkdir()
        (tf_dir / "providers.lock").write_text("lock data")

        with AtomicCompiler(output) as ac:
            (ac.staging_path / "new.tf").write_text("new resource")

        assert (output / "new.tf").exists()
        assert (output / ".terraform" / "providers.lock").exists()
        assert (output / ".terraform" / "providers.lock").read_text() == "lock data"
