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

"""Storage adapter protocol for workspace backing stores."""

from typing import Optional, Protocol


class StorageAdapter(Protocol):
    """Protocol defining the interface for workspace storage backends.

    All paths are relative to the adapter's configured root
    (base directory for local, bucket+prefix for S3).
    """

    def write(self, path: str, content: bytes) -> None:
        """Write content to the specified path."""
        ...

    def read(self, path: str) -> bytes:
        """Read and return content from the specified path."""
        ...

    def delete(self, path: str) -> None:
        """Delete the data at the specified path."""
        ...

    def list(self, prefix: Optional[str] = None) -> list[str]:
        """List relative paths, optionally filtered by prefix."""
        ...

    def exists(self, path: str) -> bool:
        """Return True if data exists at the specified path."""
        ...

    def create_directory(self, path: str) -> None:
        """Create a directory (and any intermediate directories)."""
        ...

    def delete_directory(self, path: str) -> None:
        """Delete a directory and all its contents."""
        ...
