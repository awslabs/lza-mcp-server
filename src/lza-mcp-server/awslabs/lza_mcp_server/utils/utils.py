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

"""Shared utilities for the LZA MCP Server."""

import os
import logging
import subprocess
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# AWS Configuration
DEFAULT_REGION = "us-east-1"

def get_aws_region():
    """Get AWS region using boto3's default resolution chain."""
    # Try environment variable first
    region = os.environ.get("AWS_REGION")
    if region:
        return region
    
    # Try AWS_DEFAULT_REGION (used by AWS CLI)
    region = os.environ.get("AWS_DEFAULT_REGION")
    if region:
        return region
    
    # Try boto3's session default region resolution
    try:
        session = boto3.Session()
        region = session.region_name
        if region:
            return region
    except Exception as e:
        logger.debug(f"Could not determine region from boto3 session: {e}")
    
    # Fall back to default
    logger.warning(f"No region configured, using default: {DEFAULT_REGION}")
    return DEFAULT_REGION

def get_aws_session():
    """Create an AWS session using boto3's default credential provider chain."""
    region = get_aws_region()
    logger.info(f"Creating AWS session with region: {region}")
    return boto3.Session(region_name=region)

def download_from_s3(bucket: str, key: str, local_path: str) -> bool:
    """
    Download a file from S3 to a local path.
    
    Args:
        bucket: The S3 bucket name
        key: The S3 object key
        local_path: The local file path to save to
        
    Returns:
        bool: True if successful, False otherwise
    """
    session = get_aws_session()
    s3_client = session.client('s3')
    
    try:
        s3_client.download_file(bucket, key, local_path)
        logger.info(f"Successfully downloaded {bucket}/{key} to {local_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to download {bucket}/{key}: {str(e)}")
        return False

def validate_configuration_impl(config_dir: str, _test_mode: bool = False) -> Dict[str, Any]:
    """
    Validate LZA configuration files using the native LZA validator.
    
    Args:
        config_dir: Path to the directory containing configuration files
        _test_mode: Internal flag to bypass strict validation for testing
        
    Returns:
        Dictionary containing validation results
    """
    logger.info(f"validate_configuration_impl called with config_dir={config_dir}")
    
    lza_dir = "/app/lza"
    
    try:
        # List files in config directory
        config_files = os.listdir(config_dir)
        total_files = 0
        for root, dirs, files in os.walk(config_dir):
            total_files += len(files)
        
        logger.info(f"Found {len(config_files)} files in top level and {total_files} total files in config directory")
        
        # Validate and sanitize config_dir to prevent command injection
        if _test_mode:
            # In test mode, use minimal validation to allow mocking
            sanitized_config_dir = config_dir
            safe_config_dir = config_dir
        else:
            try:
                from pathlib import Path
                config_path = Path(config_dir).resolve()
                if not config_path.exists() or not config_path.is_dir():
                    logger.error(f"Config directory does not exist or is not a directory: {config_dir}")
                    return {"valid": False, "errors": [{"message": f"Config directory not found: {config_dir}"}]}
                
                sanitized_config_dir = str(config_path)
                
            except (OSError, ValueError) as e:
                logger.error(f"Invalid config directory path: {config_dir} - {str(e)}")
                return {"valid": False, "errors": [{"message": f"Invalid config directory path: {config_dir}"}]}
        
        # Additional validation to ensure the path is safe for subprocess
        if not _test_mode:
            try:
                # Validate that the path doesn't contain dangerous characters
                import re
                if re.search(r'[;&|`$(){}[\]<>]', sanitized_config_dir):
                    logger.error(f"Config directory path contains unsafe characters: {sanitized_config_dir}")
                    return {"valid": False, "errors": [{"message": "Config directory path contains unsafe characters"}]}
                
                # Ensure the path is properly quoted/escaped by reconstructing it
                safe_config_dir = os.path.abspath(sanitized_config_dir)
                
                # Validate the safe path still exists (double-check after normalization)
                if not os.path.exists(safe_config_dir) or not os.path.isdir(safe_config_dir):
                    logger.error(f"Normalized config directory is invalid: {safe_config_dir}")
                    return {"valid": False, "errors": [{"message": "Normalized config directory is invalid"}]}
                
                # Final security measure: ensure path is within allowed boundaries
                # This prevents any potential path traversal or injection
                try:
                    # Get the real path to resolve any symlinks
                    real_path = os.path.realpath(safe_config_dir)
                    
                    # Ensure the path is absolute and doesn't contain any suspicious patterns
                    if not os.path.isabs(real_path):
                        logger.error(f"Config directory path must be absolute: {real_path}")
                        return {"valid": False, "errors": [{"message": "Config directory path must be absolute"}]}
                    
                    # Use the fully resolved and validated path
                    safe_config_dir = real_path
                    
                except (OSError, ValueError) as e:
                    logger.error(f"Error resolving config directory path: {str(e)}")
                    return {"valid": False, "errors": [{"message": f"Error resolving config directory: {str(e)}"}]}
                    
                except Exception as e:
                    logger.error(f"Error validating config directory path: {str(e)}")
                    return {"valid": False, "errors": [{"message": f"Error validating config directory: {str(e)}"}]}
                    
            except Exception as e:
                logger.error(f"Error validating config directory path: {str(e)}")
                return {"valid": False, "errors": [{"message": f"Error validating config directory: {str(e)}"}]}
        else:
            # In test mode, skip additional security validation
            safe_config_dir = sanitized_config_dir
        
        # Validate and sanitize the working directory path
        if _test_mode:
            # In test mode, use simple working directory
            safe_cwd = f"{lza_dir}/source"
        else:
            try:
                cwd_path = Path(f"{lza_dir}/source").resolve()
                if not cwd_path.exists() or not cwd_path.is_dir():
                    logger.error(f"LZA source directory does not exist: {cwd_path}")
                    return {"valid": False, "errors": [{"message": f"LZA source directory not found: {cwd_path}"}]}
                
                safe_cwd = str(cwd_path)
                
            except (OSError, ValueError) as e:
                logger.error(f"Invalid LZA source directory: {lza_dir}/source - {str(e)}")
                return {"valid": False, "errors": [{"message": f"Invalid LZA source directory: {str(e)}"}]}
        
        # Run the validation command with fully validated and safe paths
        # SECURITY: safe_config_dir has been extensively validated:
        # 1. Path existence and directory validation via Path.resolve()
        # 2. Shell metacharacter filtering via regex
        # 3. Path normalization via os.path.abspath()
        # 4. Symlink resolution via os.path.realpath()
        # 5. Absolute path validation
        # The array form of subprocess.run prevents shell injection
        # nosemgrep: dangerous-subprocess-use-audit
        cmd = ["yarn", "validate-config", safe_config_dir]
        
        logger.info(f"Executing validation command: {' '.join(cmd)} in directory {safe_cwd}")
        # nosemgrep: dangerous-subprocess-use-audit
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60,
            cwd=safe_cwd
        )
        
        # Check if validation succeeded
        if process.returncode == 0:
            logger.info("Validation succeeded")
            return {
                "valid": True,
                "message": "Configuration validation successful"
            }
        else:
            logger.error(f"Validation failed with exit code {process.returncode}")
            
            # Parse validation errors
            stdout_full = process.stdout
            stderr_full = process.stderr
            stdout_lines = stdout_full.split("\n")
            stderr_lines = stderr_full.split("\n")
            
            # Extract error patterns
            validation_errors = []
            missing_files_errors = []
            detailed_errors = []
            general_errors = []
            
            # Process error lines
            for line in stdout_lines + stderr_lines:
                line = line.strip()
                if not line:
                    continue
                
                # Look for ENOENT errors (file not found)
                if "ENOENT: no such file or directory" in line:
                    file_path = line.split("open '")[1].split("'")[0] if "open '" in line else "unknown file"
                    missing_file = os.path.basename(file_path)
                    missing_files_errors.append({
                        "message": f"Missing file: {missing_file}",
                        "path": file_path,
                        "file": missing_file,
                        "severity": "error"
                    })
                
                # Look for specific issue patterns
                if " has " in line and " issues:" in line:
                    config_file = line.split(" has ")[0]
                    issues_count = line.split(" has ")[1].split(" issues")[0]
                    detailed_errors.append({
                        "message": f"{config_file} has {issues_count} issues",
                        "file": config_file,
                        "severity": "error"
                    })
                
                # Look for validation errors
                if "validation failed" in line.lower() or "error" in line.lower():
                    general_errors.append({
                        "message": line,
                        "severity": "error"
                    })
            
            # Combine all errors
            all_validation_errors = missing_files_errors + detailed_errors + general_errors
            
            if not all_validation_errors:
                all_validation_errors = [{
                    "message": "Configuration validation failed. See diagnostics for details.",
                    "severity": "error"
                }]
            
            # Create diagnostics
            diagnostic_sections = []
            
            if missing_files_errors:
                files_section = "## Missing Files\nThe validator could not find these required files:\n"
                for err in missing_files_errors:
                    files_section += f"- {err['path']}\n"
                diagnostic_sections.append(files_section)
            
            if detailed_errors:
                details_section = "## Configuration Issues\nThe following issues were found in your configuration:\n"
                for err in detailed_errors:
                    details_section += f"- {err['message']}\n"
                diagnostic_sections.append(details_section)
            
            # Add full validator output
            full_output_section = "## Full Validator Output\n"
            if stdout_full.strip():
                full_output_section += "\nSTANDARD OUTPUT:\n" + stdout_full
            if stderr_full.strip():
                full_output_section += "\nSTANDARD ERROR:\n" + stderr_full
            diagnostic_sections.append(full_output_section)
            
            # Add recommendations
            recommendations = """
## Recommendations for Fixing Issues

1. Make sure ALL required supporting files and directories are included in your ZIP file:
   - Use `zip -r lza-config.zip .` to include all files and subdirectories
   - Include all referenced JSON files like IAM policies, SCP policies, etc.
   - Include all custom directories mentioned in the error messages

2. Check common configuration issues:
   - Ensure all resource references are valid
   - Verify account email addresses are valid and unique
   - Check for proper structure in organization units
   - Validate that all required properties are defined

3. For detailed configuration guidance, refer to:
   - LZA documentation: https://docs.aws.amazon.com/solutions/latest/landing-zone-accelerator-on-aws/welcome.html
   - Default configuration samples: https://github.com/awslabs/landing-zone-accelerator-on-aws/tree/main/reference/sample-configurations
"""
            diagnostic_sections.append(recommendations)
            
            full_diagnostics = "\n\n".join(diagnostic_sections)
            
            return {
                "valid": False,
                "errors": all_validation_errors,
                "message": "Configuration validation failed",
                "detailed_errors": detailed_errors,
                "missing_files": missing_files_errors if missing_files_errors else None,
                "diagnostics": full_diagnostics,
                "validator_output": {
                    "stdout": stdout_full,
                    "stderr": stderr_full
                }
            }
            
    except subprocess.TimeoutExpired:
        logger.error("Validation timed out after 60 seconds")
        return {
            "valid": False,
            "errors": [{"message": "Validation timed out after 60 seconds", "severity": "error"}],
            "diagnostics": "The validation process took too long and timed out. This may happen with very large configurations."
        }
    except Exception as e:
        logger.error(f"Error in validation process: {str(e)}")
        return {
            "valid": False, 
            "errors": [{"message": f"Validation error: {str(e)}", "severity": "error"}],
            "diagnostics": f"An error occurred during validation: {str(e)}"
        }