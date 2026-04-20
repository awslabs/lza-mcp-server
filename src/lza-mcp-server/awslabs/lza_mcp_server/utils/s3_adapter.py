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

"""S3 storage adapter for workspaces."""

import logging
import os
from typing import Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

logger = logging.getLogger(__name__)


class S3Adapter:
    """StorageAdapter implementation backed by Amazon S3.

    Bucket name is read from ``WORKSPACE_S3_BUCKET`` and key prefix from
    ``WORKSPACE_S3_PREFIX`` (default ``workspaces/``).  Directories are
    simulated via key prefixes — S3 has no real directory concept.
    """

    def __init__(
        self,
        bucket: Optional[str] = None,
        prefix: Optional[str] = None,
        s3_client: Optional[object] = None,
    ) -> None:
        self._bucket = bucket or os.environ.get("WORKSPACE_S3_BUCKET", "")
        if not self._bucket:
            raise ValueError(
                "WORKSPACE_S3_BUCKET environment variable must be set for S3 storage"
            )
        self._prefix = prefix or os.environ.get("WORKSPACE_S3_PREFIX", "workspaces/")
        if not self._prefix.endswith("/"):
            self._prefix += "/"
        self._client = s3_client or boto3.client("s3")

    def _key(self, path: str) -> str:
        """Build the full S3 key for a relative *path*."""
        return f"{self._prefix}{path}"

    # ------------------------------------------------------------------
    # StorageAdapter interface
    # ------------------------------------------------------------------

    def write(self, path: str, content: bytes) -> None:
        """Write *content* to the S3 object at *path*."""
        try:
            self._client.put_object(  # type: ignore[union-attr]
                Bucket=self._bucket, Key=self._key(path), Body=content
            )
        except (NoCredentialsError, PartialCredentialsError) as exc:
            raise RuntimeError(
                "AWS credentials are not configured or invalid. "
                "Please configure valid credentials to use S3 storage."
            ) from exc
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "Unknown")
            raise RuntimeError(
                f"S3 PutObject failed (error code: {code}): {exc}"
            ) from exc

    def read(self, path: str) -> bytes:
        """Read and return bytes from the S3 object at *path*."""
        try:
            resp = self._client.get_object(  # type: ignore[union-attr]
                Bucket=self._bucket, Key=self._key(path)
            )
            return resp["Body"].read()
        except (NoCredentialsError, PartialCredentialsError) as exc:
            raise RuntimeError(
                "AWS credentials are not configured or invalid. "
                "Please configure valid credentials to use S3 storage."
            ) from exc
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "Unknown")
            if code == "NoSuchKey":
                raise FileNotFoundError(f"Path not found in S3: {path}") from exc
            raise RuntimeError(
                f"S3 GetObject failed (error code: {code}): {exc}"
            ) from exc

    def delete(self, path: str) -> None:
        """Delete the S3 object at *path*."""
        try:
            self._client.delete_object(  # type: ignore[union-attr]
                Bucket=self._bucket, Key=self._key(path)
            )
        except (NoCredentialsError, PartialCredentialsError) as exc:
            raise RuntimeError(
                "AWS credentials are not configured or invalid. "
                "Please configure valid credentials to use S3 storage."
            ) from exc
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "Unknown")
            raise RuntimeError(
                f"S3 DeleteObject failed (error code: {code}): {exc}"
            ) from exc

    def list(self, prefix: Optional[str] = None) -> list[str]:
        """Return relative paths of all objects under *prefix* (or root)."""
        full_prefix = self._key(prefix) if prefix else self._prefix
        if not full_prefix.endswith("/"):
            full_prefix += "/"
        try:
            result: list[str] = []
            paginator = self._client.get_paginator("list_objects_v2")  # type: ignore[union-attr]
            for page in paginator.paginate(Bucket=self._bucket, Prefix=full_prefix):
                for obj in page.get("Contents", []):
                    key: str = obj["Key"]
                    # Skip directory marker keys (trailing slash)
                    if key.endswith("/"):
                        continue
                    # Return path relative to the adapter prefix
                    rel = key[len(self._prefix) :]
                    result.append(rel)
            return result
        except (NoCredentialsError, PartialCredentialsError) as exc:
            raise RuntimeError(
                "AWS credentials are not configured or invalid. "
                "Please configure valid credentials to use S3 storage."
            ) from exc
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "Unknown")
            raise RuntimeError(
                f"S3 ListObjectsV2 failed (error code: {code}): {exc}"
            ) from exc

    def exists(self, path: str) -> bool:
        """Return True if an object (or prefix) exists at *path*."""
        try:
            self._client.head_object(  # type: ignore[union-attr]
                Bucket=self._bucket, Key=self._key(path)
            )
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "Unknown")
            if code == "404":
                # Could be a "directory" — check for objects with this prefix
                resp = self._client.list_objects_v2(  # type: ignore[union-attr]
                    Bucket=self._bucket,
                    Prefix=self._key(path).rstrip("/") + "/",
                    MaxKeys=1,
                )
                return resp.get("KeyCount", 0) > 0
            raise RuntimeError(
                f"S3 HeadObject failed (error code: {code}): {exc}"
            ) from exc
        except (NoCredentialsError, PartialCredentialsError) as exc:
            raise RuntimeError(
                "AWS credentials are not configured or invalid. "
                "Please configure valid credentials to use S3 storage."
            ) from exc

    def create_directory(self, path: str) -> None:
        """Simulate directory creation by writing a zero-byte marker key."""
        dir_key = self._key(path).rstrip("/") + "/"
        try:
            self._client.put_object(  # type: ignore[union-attr]
                Bucket=self._bucket, Key=dir_key, Body=b""
            )
        except (NoCredentialsError, PartialCredentialsError) as exc:
            raise RuntimeError(
                "AWS credentials are not configured or invalid. "
                "Please configure valid credentials to use S3 storage."
            ) from exc
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "Unknown")
            raise RuntimeError(
                f"S3 PutObject (directory) failed (error code: {code}): {exc}"
            ) from exc

    def delete_directory(self, path: str) -> None:
        """Delete all objects under the given directory prefix."""
        dir_prefix = self._key(path).rstrip("/") + "/"
        try:
            paginator = self._client.get_paginator("list_objects_v2")  # type: ignore[union-attr]
            for page in paginator.paginate(Bucket=self._bucket, Prefix=dir_prefix):
                objects = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
                if objects:
                    self._client.delete_objects(  # type: ignore[union-attr]
                        Bucket=self._bucket, Delete={"Objects": objects}
                    )
        except (NoCredentialsError, PartialCredentialsError) as exc:
            raise RuntimeError(
                "AWS credentials are not configured or invalid. "
                "Please configure valid credentials to use S3 storage."
            ) from exc
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "Unknown")
            raise RuntimeError(
                f"S3 delete_directory failed (error code: {code}): {exc}"
            ) from exc
