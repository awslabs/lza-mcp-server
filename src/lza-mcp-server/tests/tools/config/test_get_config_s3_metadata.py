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

"""Unit tests for S3ConfigRetrieval metadata extraction."""

import pytest
import os
import tempfile
from pathlib import Path

from awslabs.lza_mcp_server.tools.config.get_config_s3 import S3ConfigRetrieval


class TestExtractZipMetadata:
    """Test ZIP metadata extraction."""

    def test_extract_metadata_simple_structure(self):
        """Test metadata extraction from simple directory structure."""
        retrieval = S3ConfigRetrieval()
        
        # Create a temporary directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create some files and directories
            Path(temp_dir, "file1.yaml").touch()
            Path(temp_dir, "file2.yaml").touch()
            Path(temp_dir, "folder1").mkdir()
            Path(temp_dir, "folder1", "nested.yaml").touch()
            
            # Create a dummy ZIP file
            zip_path = os.path.join(temp_dir, "test.zip")
            Path(zip_path).touch()
            
            metadata = retrieval._extract_zip_metadata(zip_path, temp_dir)
            
            assert metadata["file_count"] >= 2
            assert metadata["directory_count"] >= 1
            assert "file1.yaml" in metadata["root_files"]
            assert "file2.yaml" in metadata["root_files"]
            assert "folder1" in metadata["root_folders"]
            assert metadata["zip_size"] >= 0

    def test_extract_metadata_nested_structure(self):
        """Test metadata extraction from nested directory structure."""
        retrieval = S3ConfigRetrieval()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create nested structure
            Path(temp_dir, "config").mkdir()
            Path(temp_dir, "config", "accounts.yaml").touch()
            Path(temp_dir, "config", "network").mkdir()
            Path(temp_dir, "config", "network", "vpc.yaml").touch()
            
            zip_path = os.path.join(temp_dir, "test.zip")
            Path(zip_path).touch()
            
            metadata = retrieval._extract_zip_metadata(zip_path, temp_dir)
            
            assert "config" in metadata["root_folders"]
            assert "structure" in metadata
            assert "root" in metadata["structure"]
            assert "directories" in metadata["structure"]["root"]

    def test_extract_metadata_empty_directory(self):
        """Test metadata extraction from empty directory."""
        retrieval = S3ConfigRetrieval()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create extraction directory separate from zip location
            extract_dir = os.path.join(temp_dir, "extract")
            os.makedirs(extract_dir)
            
            zip_path = os.path.join(temp_dir, "test.zip")
            Path(zip_path).touch()
            
            metadata = retrieval._extract_zip_metadata(zip_path, extract_dir)
            
            assert metadata["file_count"] == 0
            assert metadata["directory_count"] == 0
            assert metadata["root_files"] == []
            assert metadata["root_folders"] == []

    def test_extract_metadata_only_files(self):
        """Test metadata extraction with only files (no directories)."""
        retrieval = S3ConfigRetrieval()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create extraction directory separate from zip location
            extract_dir = os.path.join(temp_dir, "extract")
            os.makedirs(extract_dir)
            
            # Create only files in extract directory
            Path(extract_dir, "accounts.yaml").touch()
            Path(extract_dir, "global.yaml").touch()
            Path(extract_dir, "network.yaml").touch()
            
            zip_path = os.path.join(temp_dir, "test.zip")
            Path(zip_path).touch()
            
            metadata = retrieval._extract_zip_metadata(zip_path, extract_dir)
            
            assert metadata["file_count"] == 3
            assert metadata["directory_count"] == 0
            assert len(metadata["root_files"]) == 3
            assert len(metadata["root_folders"]) == 0

    def test_extract_metadata_handles_errors_gracefully(self):
        """Test metadata extraction handles errors gracefully."""
        retrieval = S3ConfigRetrieval()
        
        # Use non-existent paths
        metadata = retrieval._extract_zip_metadata(
            "/nonexistent/zip.zip",
            "/nonexistent/extract"
        )
        
        # Should return default metadata structure without crashing
        assert "file_count" in metadata
        assert "directory_count" in metadata
        assert "root_files" in metadata
        assert "root_folders" in metadata
        assert "structure" in metadata
