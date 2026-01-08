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

"""Tests for schema integrity validation (T-015)."""

import pytest
from pathlib import Path
import tempfile
import json

from awslabs.lza_mcp_server.utils.integrity import (
    calculate_checksum,
    load_checksums,
    verify_checksum,
    verify_schema_directory,
    validate_schemas_on_startup,
)


@pytest.fixture
def temp_schema_dir():
    """Create a temporary schema directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        schema_dir = Path(tmpdir) / "json-schemas"
        schema_dir.mkdir()
        
        # Create version directories with schema files
        for version in ["v1.12.0", "v1.13.0"]:
            version_dir = schema_dir / version
            version_dir.mkdir()
            
            schema_file = version_dir / "combined.json"
            schema_file.write_text(json.dumps({
                "version": version,
                "schemas": {"test": "data"}
            }))
        
        yield schema_dir


@pytest.fixture
def temp_checksum_file(temp_schema_dir):
    """Create a checksum file for the temp schema directory."""
    checksum_file = temp_schema_dir / "checksums.sha256"
    
    checksums = []
    for version in ["v1.12.0", "v1.13.0"]:
        schema_file = temp_schema_dir / version / "combined.json"
        checksum = calculate_checksum(schema_file)
        checksums.append(f"{checksum} {version}/combined.json")
    
    checksum_file.write_text("\n".join([
        "# Test checksums",
        *checksums
    ]))
    
    return checksum_file


@pytest.mark.unit
class TestCalculateChecksum:
    """Tests for calculate_checksum function."""
    
    def test_calculate_checksum_success(self, tmp_path):
        """Test successful checksum calculation."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        checksum = calculate_checksum(test_file)
        
        assert isinstance(checksum, str)
        assert len(checksum) == 64  # SHA-256 hex length
        assert checksum.isalnum()
    
    def test_calculate_checksum_consistent(self, tmp_path):
        """Test checksum is consistent for same content."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        checksum1 = calculate_checksum(test_file)
        checksum2 = calculate_checksum(test_file)
        
        assert checksum1 == checksum2
    
    def test_calculate_checksum_different_content(self, tmp_path):
        """Test different content produces different checksums."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        
        file1.write_text("content 1")
        file2.write_text("content 2")
        
        checksum1 = calculate_checksum(file1)
        checksum2 = calculate_checksum(file2)
        
        assert checksum1 != checksum2
    
    def test_calculate_checksum_file_not_found(self, tmp_path):
        """Test error handling for missing file."""
        missing_file = tmp_path / "missing.txt"
        
        with pytest.raises(FileNotFoundError):
            calculate_checksum(missing_file)
    
    def test_calculate_checksum_large_file(self, tmp_path):
        """Test checksum calculation for large files."""
        large_file = tmp_path / "large.txt"
        # Create 10MB file
        large_file.write_text("x" * (10 * 1024 * 1024))
        
        checksum = calculate_checksum(large_file)
        
        assert isinstance(checksum, str)
        assert len(checksum) == 64


@pytest.mark.unit
class TestLoadChecksums:
    """Tests for load_checksums function."""
    
    def test_load_checksums_success(self, tmp_path):
        """Test successful checksum loading."""
        checksum_file = tmp_path / "checksums.sha256"
        checksum_file.write_text(
            "abc123 v1.12.0/combined.json\n"
            "def456 v1.13.0/combined.json\n"
        )
        
        checksums = load_checksums(checksum_file)
        
        assert len(checksums) == 2
        assert checksums["v1.12.0/combined.json"] == "abc123"
        assert checksums["v1.13.0/combined.json"] == "def456"
    
    def test_load_checksums_with_comments(self, tmp_path):
        """Test loading checksums with comment lines."""
        checksum_file = tmp_path / "checksums.sha256"
        checksum_file.write_text(
            "# This is a comment\n"
            "abc123 v1.12.0/combined.json\n"
            "# Another comment\n"
            "def456 v1.13.0/combined.json\n"
        )
        
        checksums = load_checksums(checksum_file)
        
        assert len(checksums) == 2
    
    def test_load_checksums_empty_lines(self, tmp_path):
        """Test loading checksums with empty lines."""
        checksum_file = tmp_path / "checksums.sha256"
        checksum_file.write_text(
            "abc123 v1.12.0/combined.json\n"
            "\n"
            "def456 v1.13.0/combined.json\n"
        )
        
        checksums = load_checksums(checksum_file)
        
        assert len(checksums) == 2
    
    def test_load_checksums_file_not_found(self, tmp_path):
        """Test error handling for missing checksum file."""
        missing_file = tmp_path / "missing.sha256"
        
        with pytest.raises(FileNotFoundError):
            load_checksums(missing_file)
    
    def test_load_checksums_invalid_format(self, tmp_path):
        """Test error handling for invalid format."""
        checksum_file = tmp_path / "checksums.sha256"
        checksum_file.write_text("invalid_line_without_space")
        
        with pytest.raises(ValueError, match="Invalid checksum format"):
            load_checksums(checksum_file)


@pytest.mark.unit
class TestVerifyChecksum:
    """Tests for verify_checksum function."""
    
    def test_verify_checksum_success(self, tmp_path):
        """Test successful checksum verification."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        expected = calculate_checksum(test_file)
        is_valid, message = verify_checksum(test_file, expected)
        
        assert is_valid is True
        assert "verified" in message.lower()
    
    def test_verify_checksum_mismatch(self, tmp_path):
        """Test checksum mismatch detection."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        wrong_checksum = "0" * 64
        is_valid, message = verify_checksum(test_file, wrong_checksum)
        
        assert is_valid is False
        assert "mismatch" in message.lower()
        assert wrong_checksum in message
    
    def test_verify_checksum_file_not_found(self, tmp_path):
        """Test error handling for missing file."""
        missing_file = tmp_path / "missing.txt"
        
        is_valid, message = verify_checksum(missing_file, "abc123")
        
        assert is_valid is False
        assert "not found" in message.lower()


@pytest.mark.unit
class TestVerifySchemaDirectory:
    """Tests for verify_schema_directory function."""
    
    def test_verify_schema_directory_success(self, temp_schema_dir, temp_checksum_file):
        """Test successful directory verification."""
        all_valid, results = verify_schema_directory(
            temp_schema_dir,
            temp_checksum_file
        )
        
        assert all_valid is True
        assert len(results) == 2
        assert all("verified" in msg.lower() for msg in results.values())
    
    def test_verify_schema_directory_tampering(self, temp_schema_dir, temp_checksum_file):
        """Test detection of tampered schema file."""
        # Tamper with a schema file
        schema_file = temp_schema_dir / "v1.12.0" / "combined.json"
        schema_file.write_text(json.dumps({"tampered": "data"}))
        
        all_valid, results = verify_schema_directory(
            temp_schema_dir,
            temp_checksum_file
        )
        
        assert all_valid is False
        assert any("mismatch" in msg.lower() for msg in results.values())
    
    def test_verify_schema_directory_missing_file(self, temp_schema_dir, temp_checksum_file):
        """Test detection of missing schema file."""
        # Remove a schema file
        schema_file = temp_schema_dir / "v1.12.0" / "combined.json"
        schema_file.unlink()
        
        all_valid, results = verify_schema_directory(
            temp_schema_dir,
            temp_checksum_file
        )
        
        assert all_valid is False
        assert any("not found" in msg.lower() for msg in results.values())
    
    def test_verify_schema_directory_extra_file_strict(self, temp_schema_dir, temp_checksum_file):
        """Test detection of extra schema file in strict mode."""
        # Add an extra schema file not in checksums
        extra_dir = temp_schema_dir / "v1.14.0"
        extra_dir.mkdir()
        extra_file = extra_dir / "combined.json"
        extra_file.write_text(json.dumps({"extra": "data"}))
        
        all_valid, results = verify_schema_directory(
            temp_schema_dir,
            temp_checksum_file,
            strict=True
        )
        
        assert all_valid is False
        assert any("not in checksum manifest" in msg for msg in results.values())
    
    def test_verify_schema_directory_no_checksum_file(self, temp_schema_dir):
        """Test handling of missing checksum file."""
        all_valid, results = verify_schema_directory(
            temp_schema_dir,
            temp_schema_dir / "missing.sha256"
        )
        
        assert all_valid is False
        assert "error" in results


@pytest.mark.unit
class TestValidateSchemasOnStartup:
    """Tests for validate_schemas_on_startup function."""
    
    def test_validate_schemas_on_startup_success(self, temp_schema_dir, temp_checksum_file):
        """Test successful startup validation."""
        result = validate_schemas_on_startup(
            schema_dir=temp_schema_dir,
            checksum_file=temp_checksum_file,
            fail_on_error=False
        )
        
        assert result is True
    
    def test_validate_schemas_on_startup_failure_no_raise(self, temp_schema_dir, temp_checksum_file):
        """Test validation failure without raising exception."""
        # Tamper with a file
        schema_file = temp_schema_dir / "v1.12.0" / "combined.json"
        schema_file.write_text(json.dumps({"tampered": "data"}))
        
        result = validate_schemas_on_startup(
            schema_dir=temp_schema_dir,
            checksum_file=temp_checksum_file,
            fail_on_error=False
        )
        
        assert result is False
    
    def test_validate_schemas_on_startup_failure_raise(self, temp_schema_dir, temp_checksum_file):
        """Test validation failure raises exception."""
        # Tamper with a file
        schema_file = temp_schema_dir / "v1.12.0" / "combined.json"
        schema_file.write_text(json.dumps({"tampered": "data"}))
        
        with pytest.raises(RuntimeError, match="Schema integrity validation failed"):
            validate_schemas_on_startup(
                schema_dir=temp_schema_dir,
                checksum_file=temp_checksum_file,
                fail_on_error=True
            )
    
    def test_validate_schemas_on_startup_missing_dir(self, tmp_path):
        """Test handling of missing schema directory."""
        missing_dir = tmp_path / "missing"
        
        with pytest.raises(RuntimeError):
            validate_schemas_on_startup(
                schema_dir=missing_dir,
                fail_on_error=True
            )
