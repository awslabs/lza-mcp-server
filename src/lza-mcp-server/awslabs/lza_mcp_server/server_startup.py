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

"""Server startup and initialization logic."""

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_schema_directory() -> Path:
    """Get schema directory path from environment or default.

    Returns:
        Path: Schema directory path
    """
    return Path(os.environ.get("LZA_SCHEMA_DIR", "/app/json-schemas"))


def validate_schema_integrity(schema_dir: Path, fail_on_error: bool = True) -> None:
    """Validate schema integrity on startup.

    Args:
        schema_dir: Path to schema directory
        fail_on_error: Whether to raise exception on validation failure

    Raises:
        ImportError: If integrity module is not available
        Exception: If validation fails and fail_on_error is True
    """
    try:
        from .utils.integrity import validate_schemas_on_startup

        # Validate schemas - fail fast if tampering detected
        validate_schemas_on_startup(schema_dir=schema_dir, fail_on_error=fail_on_error)
    except ImportError:
        logger.warning("Schema integrity validation module not available")
        raise
    except Exception as e:
        logger.error(f"Schema integrity validation failed: {e}")
        raise


def configure_logging(log_level: str = None) -> None:
    """Configure logging for the server.

    Args:
        log_level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
                  If None, reads from FASTMCP_LOG_LEVEL environment variable.
    """
    if log_level is None:
        log_level = os.environ.get("FASTMCP_LOG_LEVEL", "INFO")

    logging.basicConfig(level=logging.INFO)
    logging.getLogger().setLevel(log_level)
