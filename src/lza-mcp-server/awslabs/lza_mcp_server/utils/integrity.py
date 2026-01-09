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

"""Schema integrity validation using SHA-256 checksums.

This module implements T-015 (Template and schema integrity validation) to detect
tampering with embedded LZA JSON schemas. Checksums are generated at build time
and validated at server startup.
"""

import hashlib
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)


def calculate_checksum(file_path: Path) -> str:
    """Calculate SHA-256 checksum of a file.

    Args:
        file_path: Path to file to checksum

    Returns:
        Hexadecimal SHA-256 checksum string

    Raises:
        FileNotFoundError: If file doesn't exist
        IOError: If file cannot be read
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    sha256_hash = hashlib.sha256()

    # Read file in chunks to handle large files efficiently
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)

    return sha256_hash.hexdigest()


def load_checksums(checksum_file: Path) -> Dict[str, str]:
    """Load checksums from a checksum manifest file.

    Expected format (one per line):
        <checksum> <relative_path>

    Example:
        abc123... v1.12.0/combined.json
        def456... v1.13.0/combined.json

    Args:
        checksum_file: Path to checksum manifest file

    Returns:
        Dictionary mapping relative paths to checksums

    Raises:
        FileNotFoundError: If checksum file doesn't exist
        ValueError: If checksum file format is invalid
    """
    if not checksum_file.exists():
        raise FileNotFoundError(f"Checksum file not found: {checksum_file}")

    checksums = {}

    with open(checksum_file, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split(None, 1)  # Split on whitespace, max 2 parts
            if len(parts) != 2:
                raise ValueError(
                    f"Invalid checksum format at line {line_num}: {line}\n"
                    f"Expected: <checksum> <path>"
                )

            checksum, path = parts
            checksums[path] = checksum

    return checksums


def verify_checksum(file_path: Path, expected_checksum: str) -> Tuple[bool, str]:
    """Verify file checksum matches expected value.

    Args:
        file_path: Path to file to verify
        expected_checksum: Expected SHA-256 checksum (hex string)

    Returns:
        Tuple of (is_valid, message):
            - is_valid: True if checksum matches, False otherwise
            - message: Success message or error details
    """
    try:
        actual_checksum = calculate_checksum(file_path)

        if actual_checksum == expected_checksum:
            return True, f"Checksum verified: {file_path.name}"
        else:
            return False, (
                f"Checksum mismatch for {file_path}:\n"
                f"  Expected: {expected_checksum}\n"
                f"  Actual:   {actual_checksum}\n"
                f"  This may indicate file tampering or corruption."
            )
    except FileNotFoundError as e:
        return False, f"File not found: {e}"
    except IOError as e:
        return False, f"Error reading file: {e}"


def verify_schema_directory(
    schema_dir: Path, checksum_file: Optional[Path] = None, strict: bool = True
) -> Tuple[bool, Dict[str, str]]:
    """Verify integrity of all schema files in a directory.

    Args:
        schema_dir: Directory containing schema files (e.g., /app/json-schemas)
        checksum_file: Path to checksum manifest. If None, looks for
                      'checksums.sha256' in schema_dir
        strict: If True, fail if any schema file is missing from checksums

    Returns:
        Tuple of (all_valid, results):
            - all_valid: True if all checksums match
            - results: Dictionary mapping file paths to validation messages

    Raises:
        FileNotFoundError: If schema_dir or checksum_file doesn't exist
    """
    if not schema_dir.exists():
        raise FileNotFoundError(f"Schema directory not found: {schema_dir}")

    if checksum_file is None:
        checksum_file = schema_dir / "checksums.sha256"

    # Load expected checksums
    try:
        expected_checksums = load_checksums(checksum_file)
    except FileNotFoundError:
        logger.warning(f"No checksum file found at {checksum_file}")
        return False, {"error": f"Checksum file not found: {checksum_file}"}

    results = {}
    all_valid = True

    # Verify each schema file
    for relative_path, expected_checksum in expected_checksums.items():
        file_path = schema_dir / relative_path

        is_valid, message = verify_checksum(file_path, expected_checksum)
        results[relative_path] = message

        if not is_valid:
            all_valid = False
            logger.error(f"Schema integrity check failed: {message}")
        else:
            logger.debug(f"Schema integrity verified: {relative_path}")

    # Check for schema files not in checksum manifest (if strict mode)
    if strict:
        schema_files = set()
        for version_dir in schema_dir.iterdir():
            if version_dir.is_dir() and not version_dir.name.startswith("."):
                combined_json = version_dir / "combined.json"
                if combined_json.exists():
                    relative = combined_json.relative_to(schema_dir)
                    schema_files.add(str(relative))

        unchecked_files = schema_files - set(expected_checksums.keys())
        if unchecked_files:
            all_valid = False
            for file in unchecked_files:
                msg = f"Schema file not in checksum manifest: {file}"
                results[file] = msg
                logger.error(msg)

    return all_valid, results


def validate_schemas_on_startup(
    schema_dir: Path = Path("/app/json-schemas"),
    checksum_file: Optional[Path] = None,
    fail_on_error: bool = True,
) -> bool:
    """Validate schema integrity at server startup.

    This is the main entry point for T-015 validation. Call this during
    server initialization to ensure schema files haven't been tampered with.

    Args:
        schema_dir: Directory containing versioned schema files
        checksum_file: Path to checksum manifest (default: schema_dir/checksums.sha256)
        fail_on_error: If True, raise RuntimeError on validation failure

    Returns:
        True if all schemas are valid, False otherwise

    Raises:
        RuntimeError: If validation fails and fail_on_error is True
    """
    logger.info("Starting schema integrity validation (T-015)")
    logger.info(f"Schema directory: {schema_dir}")

    try:
        all_valid, results = verify_schema_directory(
            schema_dir=schema_dir, checksum_file=checksum_file, strict=True
        )

        if all_valid:
            logger.info(
                f"✓ Schema integrity validation passed ({len(results)} files verified)"
            )
            return True
        else:
            error_msg = "Schema integrity validation FAILED:\n"
            for path, message in results.items():
                if "mismatch" in message.lower() or "not found" in message.lower():
                    error_msg += f"  - {message}\n"

            logger.error(error_msg)

            if fail_on_error:
                raise RuntimeError(
                    "Schema integrity validation failed. "
                    "This may indicate file tampering or corruption. "
                    "Refusing to start server."
                )

            return False

    except FileNotFoundError as e:
        logger.warning(f"Schema integrity validation skipped: {e}")
        if fail_on_error:
            raise RuntimeError(f"Cannot validate schema integrity: {e}")
        return False
