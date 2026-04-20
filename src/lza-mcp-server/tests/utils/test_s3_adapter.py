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

"""Unit tests for S3Adapter using moto mock."""

import boto3
import pytest
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
from moto import mock_aws
from unittest.mock import Mock, MagicMock

from awslabs.lza_mcp_server.utils.s3_adapter import S3Adapter

BUCKET = "test-workspace-bucket"
PREFIX = "workspaces/"


@pytest.fixture
def s3_adapter():
    """Create an S3Adapter backed by a moto-mocked S3 bucket."""
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        adapter = S3Adapter(bucket=BUCKET, prefix=PREFIX, s3_client=client)
        yield adapter


class TestS3AdapterWriteRead:
    """Test write and read operations."""

    def test_write_read_roundtrip(self, s3_adapter):
        """Written content can be read back identically."""
        s3_adapter.write("hello.txt", b"world")
        assert s3_adapter.read("hello.txt") == b"world"

    def test_write_nested_path(self, s3_adapter):
        """Nested paths work correctly."""
        s3_adapter.write("a/b/c/file.txt", b"deep")
        assert s3_adapter.read("a/b/c/file.txt") == b"deep"

    def test_write_overwrites(self, s3_adapter):
        """Writing to an existing key overwrites the content."""
        s3_adapter.write("f.txt", b"first")
        s3_adapter.write("f.txt", b"second")
        assert s3_adapter.read("f.txt") == b"second"

    def test_read_nonexistent_raises(self, s3_adapter):
        """Reading a missing key raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            s3_adapter.read("does_not_exist.txt")


class TestS3AdapterDelete:
    """Test delete operations."""

    def test_delete_removes_object(self, s3_adapter):
        """Deleting an object removes it."""
        s3_adapter.write("rm_me.txt", b"bye")
        assert s3_adapter.exists("rm_me.txt")
        s3_adapter.delete("rm_me.txt")
        assert not s3_adapter.exists("rm_me.txt")

    def test_delete_nonexistent_is_noop(self, s3_adapter):
        """Deleting a non-existent key does not raise."""
        s3_adapter.delete("ghost.txt")  # should not raise


class TestS3AdapterList:
    """Test list operations."""

    def test_list_all(self, s3_adapter):
        """Listing without prefix returns all objects."""
        s3_adapter.write("a.txt", b"1")
        s3_adapter.write("sub/b.txt", b"2")
        result = sorted(s3_adapter.list())
        assert result == ["a.txt", "sub/b.txt"]

    def test_list_with_prefix(self, s3_adapter):
        """Listing with prefix returns only matching objects."""
        s3_adapter.write("x/one.txt", b"1")
        s3_adapter.write("x/two.txt", b"2")
        s3_adapter.write("y/three.txt", b"3")
        result = sorted(s3_adapter.list(prefix="x"))
        assert result == ["x/one.txt", "x/two.txt"]

    def test_list_empty(self, s3_adapter):
        """Listing an empty bucket returns an empty list."""
        assert s3_adapter.list() == []

    def test_list_skips_directory_markers(self, s3_adapter):
        """Directory marker keys (trailing slash) are excluded."""
        s3_adapter.create_directory("mydir")
        s3_adapter.write("mydir/file.txt", b"data")
        result = s3_adapter.list()
        assert "mydir/file.txt" in result
        # The directory marker should not appear
        assert all(not r.endswith("/") for r in result)


class TestS3AdapterExists:
    """Test exists operations."""

    def test_exists_object(self, s3_adapter):
        """Exists returns True for an existing object."""
        s3_adapter.write("present.txt", b"here")
        assert s3_adapter.exists("present.txt") is True

    def test_exists_directory_prefix(self, s3_adapter):
        """Exists returns True for a directory prefix with children."""
        s3_adapter.write("dir/file.txt", b"data")
        assert s3_adapter.exists("dir") is True

    def test_not_exists(self, s3_adapter):
        """Exists returns False for missing paths."""
        assert s3_adapter.exists("missing") is False


class TestS3AdapterDirectories:
    """Test create_directory and delete_directory."""

    def test_create_directory(self, s3_adapter):
        """create_directory creates a marker key."""
        s3_adapter.create_directory("new_folder")
        assert s3_adapter.exists("new_folder") is True

    def test_delete_directory(self, s3_adapter):
        """delete_directory removes all objects under the prefix."""
        s3_adapter.write("dir/a.txt", b"1")
        s3_adapter.write("dir/b.txt", b"2")
        s3_adapter.delete_directory("dir")
        assert s3_adapter.list(prefix="dir") == []

    def test_delete_directory_nonexistent_is_noop(self, s3_adapter):
        """Deleting a non-existent directory does not raise."""
        s3_adapter.delete_directory("no_such_dir")  # should not raise


class TestS3AdapterErrors:
    """Test error wrapping and credential failure handling."""

    def test_write_client_error(self):
        """ClientError on write is wrapped with S3 error code."""
        mock_client = Mock()
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}
        mock_client.put_object.side_effect = ClientError(error_response, "PutObject")
        adapter = S3Adapter(bucket=BUCKET, prefix=PREFIX, s3_client=mock_client)

        with pytest.raises(RuntimeError, match="AccessDenied"):
            adapter.write("test.txt", b"data")

    def test_read_client_error(self):
        """ClientError on read is wrapped with S3 error code."""
        mock_client = Mock()
        error_response = {"Error": {"Code": "InternalError", "Message": "Oops"}}
        mock_client.get_object.side_effect = ClientError(error_response, "GetObject")
        adapter = S3Adapter(bucket=BUCKET, prefix=PREFIX, s3_client=mock_client)

        with pytest.raises(RuntimeError, match="InternalError"):
            adapter.read("test.txt")

    def test_write_no_credentials(self):
        """NoCredentialsError on write produces a descriptive auth error."""
        mock_client = Mock()
        mock_client.put_object.side_effect = NoCredentialsError()
        adapter = S3Adapter(bucket=BUCKET, prefix=PREFIX, s3_client=mock_client)

        with pytest.raises(RuntimeError, match="credentials"):
            adapter.write("test.txt", b"data")

    def test_read_no_credentials(self):
        """NoCredentialsError on read produces a descriptive auth error."""
        mock_client = Mock()
        mock_client.get_object.side_effect = NoCredentialsError()
        adapter = S3Adapter(bucket=BUCKET, prefix=PREFIX, s3_client=mock_client)

        with pytest.raises(RuntimeError, match="credentials"):
            adapter.read("test.txt")

    def test_delete_client_error(self):
        """ClientError on delete is wrapped with S3 error code."""
        mock_client = Mock()
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}
        mock_client.delete_object.side_effect = ClientError(
            error_response, "DeleteObject"
        )
        adapter = S3Adapter(bucket=BUCKET, prefix=PREFIX, s3_client=mock_client)

        with pytest.raises(RuntimeError, match="AccessDenied"):
            adapter.delete("test.txt")

    def test_prefix_auto_appends_slash(self):
        """Prefix without trailing slash gets one appended."""
        adapter = S3Adapter(bucket=BUCKET, prefix="no_slash", s3_client=Mock())
        assert adapter._prefix == "no_slash/"

    def test_delete_no_credentials(self):
        """NoCredentialsError on delete produces a descriptive auth error."""
        mock_client = Mock()
        mock_client.delete_object.side_effect = NoCredentialsError()
        adapter = S3Adapter(bucket=BUCKET, prefix=PREFIX, s3_client=mock_client)

        with pytest.raises(RuntimeError, match="credentials"):
            adapter.delete("test.txt")

    def test_list_client_error(self):
        """ClientError on list is wrapped with S3 error code."""
        mock_client = Mock()
        paginator = MagicMock()
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}
        paginator.paginate.side_effect = ClientError(error_response, "ListObjectsV2")
        mock_client.get_paginator.return_value = paginator
        adapter = S3Adapter(bucket=BUCKET, prefix=PREFIX, s3_client=mock_client)

        with pytest.raises(RuntimeError, match="AccessDenied"):
            adapter.list()

    def test_list_no_credentials(self):
        """NoCredentialsError on list produces a descriptive auth error."""
        mock_client = Mock()
        paginator = MagicMock()
        paginator.paginate.side_effect = NoCredentialsError()
        mock_client.get_paginator.return_value = paginator
        adapter = S3Adapter(bucket=BUCKET, prefix=PREFIX, s3_client=mock_client)

        with pytest.raises(RuntimeError, match="credentials"):
            adapter.list()

    def test_exists_client_error_non_404(self):
        """ClientError on exists with non-404 code raises RuntimeError."""
        mock_client = Mock()
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}
        mock_client.head_object.side_effect = ClientError(error_response, "HeadObject")
        adapter = S3Adapter(bucket=BUCKET, prefix=PREFIX, s3_client=mock_client)

        with pytest.raises(RuntimeError, match="AccessDenied"):
            adapter.exists("test.txt")

    def test_exists_no_credentials(self):
        """NoCredentialsError on exists produces a descriptive auth error."""
        mock_client = Mock()
        mock_client.head_object.side_effect = NoCredentialsError()
        adapter = S3Adapter(bucket=BUCKET, prefix=PREFIX, s3_client=mock_client)

        with pytest.raises(RuntimeError, match="credentials"):
            adapter.exists("test.txt")

    def test_create_directory_client_error(self):
        """ClientError on create_directory is wrapped with S3 error code."""
        mock_client = Mock()
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}
        mock_client.put_object.side_effect = ClientError(error_response, "PutObject")
        adapter = S3Adapter(bucket=BUCKET, prefix=PREFIX, s3_client=mock_client)

        with pytest.raises(RuntimeError, match="AccessDenied"):
            adapter.create_directory("mydir")

    def test_create_directory_no_credentials(self):
        """NoCredentialsError on create_directory produces auth error."""
        mock_client = Mock()
        mock_client.put_object.side_effect = NoCredentialsError()
        adapter = S3Adapter(bucket=BUCKET, prefix=PREFIX, s3_client=mock_client)

        with pytest.raises(RuntimeError, match="credentials"):
            adapter.create_directory("mydir")

    def test_delete_directory_client_error(self):
        """ClientError on delete_directory is wrapped with S3 error code."""
        mock_client = Mock()
        paginator = MagicMock()
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}
        paginator.paginate.side_effect = ClientError(error_response, "ListObjectsV2")
        mock_client.get_paginator.return_value = paginator
        adapter = S3Adapter(bucket=BUCKET, prefix=PREFIX, s3_client=mock_client)

        with pytest.raises(RuntimeError, match="AccessDenied"):
            adapter.delete_directory("mydir")

    def test_delete_directory_no_credentials(self):
        """NoCredentialsError on delete_directory produces auth error."""
        mock_client = Mock()
        paginator = MagicMock()
        paginator.paginate.side_effect = NoCredentialsError()
        mock_client.get_paginator.return_value = paginator
        adapter = S3Adapter(bucket=BUCKET, prefix=PREFIX, s3_client=mock_client)

        with pytest.raises(RuntimeError, match="credentials"):
            adapter.delete_directory("mydir")

    def test_partial_credentials_error(self):
        """PartialCredentialsError produces a descriptive auth error."""
        mock_client = Mock()
        mock_client.put_object.side_effect = PartialCredentialsError(
            provider="env", cred_var="AWS_SECRET_ACCESS_KEY"
        )
        adapter = S3Adapter(bucket=BUCKET, prefix=PREFIX, s3_client=mock_client)

        with pytest.raises(RuntimeError, match="credentials"):
            adapter.write("test.txt", b"data")


class TestS3AdapterConfig:
    """Test environment variable configuration."""

    def test_env_var_bucket(self, monkeypatch):
        """WORKSPACE_S3_BUCKET env var is used when no bucket arg given."""
        monkeypatch.setenv("WORKSPACE_S3_BUCKET", "my-env-bucket")
        adapter = S3Adapter(s3_client=Mock())
        assert adapter._bucket == "my-env-bucket"

    def test_env_var_prefix(self, monkeypatch):
        """WORKSPACE_S3_PREFIX env var is used when no prefix arg given."""
        monkeypatch.setenv("WORKSPACE_S3_PREFIX", "custom/prefix/")
        adapter = S3Adapter(bucket=BUCKET, s3_client=Mock())
        assert adapter._prefix == "custom/prefix/"

    def test_default_prefix(self, monkeypatch):
        """Default prefix is workspaces/ when env var is not set."""
        monkeypatch.delenv("WORKSPACE_S3_PREFIX", raising=False)
        adapter = S3Adapter(bucket=BUCKET, s3_client=Mock())
        assert adapter._prefix == "workspaces/"

    def test_missing_bucket_raises_error(self, monkeypatch):
        """Missing WORKSPACE_S3_BUCKET raises ValueError at init time."""
        monkeypatch.delenv("WORKSPACE_S3_BUCKET", raising=False)
        with pytest.raises(ValueError, match="WORKSPACE_S3_BUCKET"):
            S3Adapter(s3_client=Mock())

    def test_key_builds_correct_path(self):
        """_key() combines prefix and relative path correctly."""
        adapter = S3Adapter(bucket=BUCKET, prefix="pfx/", s3_client=Mock())
        assert adapter._key("some/file.txt") == "pfx/some/file.txt"
