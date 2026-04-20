# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for LocalAdapter."""

import pytest

from awslabs.lza_mcp_server.utils.local_adapter import LocalAdapter


class TestLocalAdapterInit:
    """Test initialization and base directory creation."""

    def test_creates_base_dir_on_init(self, tmp_path):
        """Base directory is created automatically."""
        base = tmp_path / "new_dir"
        assert not base.exists()
        LocalAdapter(base_dir=str(base))
        assert base.is_dir()

    def test_uses_env_var(self, tmp_path, monkeypatch):
        """WORKSPACE_DIR env var is respected."""
        target = tmp_path / "env_dir"
        monkeypatch.setenv("WORKSPACE_DIR", str(target))
        adapter = LocalAdapter()
        assert adapter._base_dir == target
        assert target.is_dir()

    def test_default_base_dir(self, monkeypatch):
        """Raises RuntimeError when WORKSPACE_DIR env var is not set."""
        monkeypatch.delenv("WORKSPACE_DIR", raising=False)
        import pytest

        with pytest.raises(
            RuntimeError, match="WORKSPACE_DIR environment variable is required"
        ):
            LocalAdapter()


class TestLocalAdapterWriteRead:
    """Test write and read operations."""

    def test_write_read_roundtrip(self, tmp_path):
        """Written content can be read back identically."""
        adapter = LocalAdapter(base_dir=str(tmp_path))
        adapter.write("hello.txt", b"world")
        assert adapter.read("hello.txt") == b"world"

    def test_write_creates_intermediate_dirs(self, tmp_path):
        """Intermediate directories are created for nested paths."""
        adapter = LocalAdapter(base_dir=str(tmp_path))
        adapter.write("a/b/c/file.txt", b"deep")
        assert adapter.read("a/b/c/file.txt") == b"deep"

    def test_write_overwrites_existing(self, tmp_path):
        """Writing to an existing path overwrites the content."""
        adapter = LocalAdapter(base_dir=str(tmp_path))
        adapter.write("f.txt", b"first")
        adapter.write("f.txt", b"second")
        assert adapter.read("f.txt") == b"second"

    def test_read_nonexistent_raises(self, tmp_path):
        """Reading a missing path raises FileNotFoundError."""
        adapter = LocalAdapter(base_dir=str(tmp_path))
        with pytest.raises(FileNotFoundError):
            adapter.read("does_not_exist.txt")


class TestLocalAdapterDelete:
    """Test delete operations."""

    def test_delete_removes_file(self, tmp_path):
        """Deleting a file removes it from disk."""
        adapter = LocalAdapter(base_dir=str(tmp_path))
        adapter.write("rm_me.txt", b"bye")
        assert adapter.exists("rm_me.txt")
        adapter.delete("rm_me.txt")
        assert not adapter.exists("rm_me.txt")

    def test_delete_nonexistent_is_noop(self, tmp_path):
        """Deleting a non-existent file does not raise."""
        adapter = LocalAdapter(base_dir=str(tmp_path))
        adapter.delete("ghost.txt")  # should not raise


class TestLocalAdapterList:
    """Test list operations."""

    def test_list_all_files(self, tmp_path):
        """Listing without prefix returns all files."""
        adapter = LocalAdapter(base_dir=str(tmp_path))
        adapter.write("a.txt", b"1")
        adapter.write("sub/b.txt", b"2")
        result = sorted(adapter.list())
        assert result == ["a.txt", "sub/b.txt"]

    def test_list_with_prefix(self, tmp_path):
        """Listing with prefix returns only matching files."""
        adapter = LocalAdapter(base_dir=str(tmp_path))
        adapter.write("x/one.txt", b"1")
        adapter.write("x/two.txt", b"2")
        adapter.write("y/three.txt", b"3")
        result = sorted(adapter.list(prefix="x"))
        assert result == ["x/one.txt", "x/two.txt"]

    def test_list_empty(self, tmp_path):
        """Listing an empty directory returns an empty list."""
        adapter = LocalAdapter(base_dir=str(tmp_path))
        assert adapter.list() == []

    def test_list_nonexistent_prefix(self, tmp_path):
        """Listing a non-existent prefix returns an empty list."""
        adapter = LocalAdapter(base_dir=str(tmp_path))
        assert adapter.list(prefix="nope") == []


class TestLocalAdapterExists:
    """Test exists operations."""

    def test_exists_file(self, tmp_path):
        """Exists returns True for a file."""
        adapter = LocalAdapter(base_dir=str(tmp_path))
        adapter.write("present.txt", b"here")
        assert adapter.exists("present.txt") is True

    def test_exists_directory(self, tmp_path):
        """Exists returns True for a directory."""
        adapter = LocalAdapter(base_dir=str(tmp_path))
        adapter.create_directory("mydir")
        assert adapter.exists("mydir") is True

    def test_not_exists(self, tmp_path):
        """Exists returns False for missing paths."""
        adapter = LocalAdapter(base_dir=str(tmp_path))
        assert adapter.exists("missing") is False


class TestLocalAdapterDirectories:
    """Test create_directory and delete_directory."""

    def test_create_directory(self, tmp_path):
        """create_directory creates the directory."""
        adapter = LocalAdapter(base_dir=str(tmp_path))
        adapter.create_directory("new_folder")
        assert (tmp_path / "new_folder").is_dir()

    def test_create_nested_directory(self, tmp_path):
        """create_directory creates intermediate directories."""
        adapter = LocalAdapter(base_dir=str(tmp_path))
        adapter.create_directory("a/b/c")
        assert (tmp_path / "a" / "b" / "c").is_dir()

    def test_create_directory_idempotent(self, tmp_path):
        """Creating an existing directory does not raise."""
        adapter = LocalAdapter(base_dir=str(tmp_path))
        adapter.create_directory("dup")
        adapter.create_directory("dup")  # should not raise

    def test_delete_directory(self, tmp_path):
        """delete_directory removes the directory and contents."""
        adapter = LocalAdapter(base_dir=str(tmp_path))
        adapter.write("dir/file.txt", b"data")
        adapter.delete_directory("dir")
        assert not (tmp_path / "dir").exists()

    def test_delete_directory_nonexistent_is_noop(self, tmp_path):
        """Deleting a non-existent directory does not raise."""
        adapter = LocalAdapter(base_dir=str(tmp_path))
        adapter.delete_directory("no_such_dir")  # should not raise
