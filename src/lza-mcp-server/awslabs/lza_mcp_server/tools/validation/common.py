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


import logging
import json
import yaml
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


def validate_configuration_impl(
    config_dir: str, _test_mode: bool = False
) -> Dict[str, Any]:
    """
    Validate LZA configuration files using native Python validation.

    Args:
        config_dir: Path to the directory containing configuration files
        _test_mode: Internal flag to bypass strict validation for testing

    Returns:
        Dictionary containing validation results
    """
    logger.info(f"validate_configuration_impl called with config_dir={config_dir}")

    try:
        # Validate config directory path
        config_path = Path(config_dir).resolve()
        if not config_path.exists() or not config_path.is_dir():
            logger.error(
                f"Config directory does not exist or is not a directory: {config_dir}"
            )
            return {
                "valid": False,
                "errors": [{"message": f"Config directory not found: {config_dir}"}],
            }

        # Count files for logging
        total_files = sum(1 for _ in config_path.rglob("*") if _.is_file())
        logger.info(f"Found {total_files} total files in config directory")

        # Validate configuration files
        errors = []
        valid_extensions = {".yaml", ".yml", ".json"}

        for config_file in config_path.rglob("*"):
            if not config_file.is_file() or config_file.suffix not in valid_extensions:
                continue

            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    if config_file.suffix in [".yaml", ".yml"]:
                        yaml.safe_load(f)
                    elif config_file.suffix == ".json":
                        json.load(f)

            except yaml.YAMLError as e:
                errors.append(
                    {
                        "message": f"YAML syntax error in {config_file.name}: {str(e)}",
                        "path": str(config_file),
                        "file": config_file.name,
                        "severity": "error",
                    }
                )
            except json.JSONDecodeError as e:
                errors.append(
                    {
                        "message": f"JSON syntax error in {config_file.name}: {str(e)}",
                        "path": str(config_file),
                        "file": config_file.name,
                        "severity": "error",
                    }
                )
            except Exception as e:
                errors.append(
                    {
                        "message": f"Error reading {config_file.name}: {str(e)}",
                        "path": str(config_file),
                        "file": config_file.name,
                        "severity": "error",
                    }
                )

        # Check for required files (basic LZA structure validation)
        if not _test_mode:
            required_files = [
                "accounts-config.yaml",
                "global-config.yaml",
                "organization-config.yaml",
            ]
            for required_file in required_files:
                if not (config_path / required_file).exists():
                    errors.append(
                        {
                            "message": f"Missing required file: {required_file}",
                            "path": str(config_path / required_file),
                            "file": required_file,
                            "severity": "error",
                        }
                    )

        if errors:
            logger.error(f"Validation failed with {len(errors)} errors")
            return {
                "valid": False,
                "errors": errors,
                "message": f"Configuration validation failed with {len(errors)} errors",
            }
        else:
            logger.info("Validation succeeded")
            return {"valid": True, "message": "Configuration validation successful"}

    except Exception as e:
        logger.error(f"Unexpected error during validation: {str(e)}")
        return {
            "valid": False,
            "errors": [{"message": f"Validation error: {str(e)}", "severity": "error"}],
        }
