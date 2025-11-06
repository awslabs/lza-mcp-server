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

"""Validation-related MCP tools for the LZA MCP Server."""

import os
import tempfile
import zipfile
import logging
import shutil
from typing import Dict, Any, Optional
from mcp.server.fastmcp import Context
from ...aws_access import download_from_s3, get_aws_session
from ...utils import validate_configuration_impl


logger = logging.getLogger(__name__)

async def _discover_lza_configurations(ctx: Context, workspace_path: str) -> list:
    """Discover LZA configurations in the workspace."""
    discovered_configs = []
    
    # Search for directories containing both accounts-config.yaml and organization-config.yaml
    for root, dirs, files in os.walk(workspace_path):
        if 'accounts-config.yaml' in files and 'organization-config.yaml' in files:
            discovered_configs.append(root)
            await ctx.info(f"Found LZA configuration in: {root}")
    
    return discovered_configs

async def _select_configuration(ctx: Context, discovered_configs: list) -> str:
    """Select configuration from discovered options."""
    if len(discovered_configs) == 1:
        selected = discovered_configs[0]
        await ctx.info(f"Using single discovered configuration: {selected}")
        return selected
    
    # For multiple configs, use the first one (in a real implementation, 
    # this would prompt the user)
    selected = discovered_configs[0]
    await ctx.info(f"Multiple configurations found, using: {selected}")
    return selected

async def _create_zip_with_bash(ctx: Context, config_path: str, local_share_path: str) -> Dict[str, Any]:
    """Create ZIP file using bash commands."""
    try:
        import subprocess
        
        # Expand the local share path
        expanded_path = os.path.expanduser(local_share_path)
        
        # Create the directory
        os.makedirs(expanded_path, exist_ok=True)
        
        zip_file_path = os.path.join(expanded_path, "config.zip")
        
        # Validate and sanitize config_path to prevent command injection
        try:
            from pathlib import Path
            config_dir_path = Path(config_path).resolve()
            if not config_dir_path.exists() or not config_dir_path.is_dir():
                error_msg = f"Config directory does not exist or is not a directory: {config_path}"
                await ctx.error(error_msg)
                return {"success": False, "error": error_msg}
            
            sanitized_config_path = str(config_dir_path)
            
        except (OSError, ValueError) as e:
            error_msg = f"Invalid config directory path: {config_path} - {str(e)}"
            await ctx.error(error_msg)
            return {"success": False, "error": error_msg}
        
        # Validate and sanitize zip_file_path to prevent command injection
        try:
            zip_file_dir = Path(zip_file_path).parent.resolve()
            zip_file_name = Path(zip_file_path).name
            
            # Validate zip file name to prevent injection
            if not zip_file_name or '..' in zip_file_name or '/' in zip_file_name:
                error_msg = f"Invalid ZIP file name: {zip_file_name}"
                await ctx.error(error_msg)
                return {"success": False, "error": error_msg}
            
            # Ensure the zip file directory exists and is safe
            if not zip_file_dir.exists():
                error_msg = f"ZIP file directory does not exist: {zip_file_dir}"
                await ctx.error(error_msg)
                return {"success": False, "error": error_msg}
            
            # Reconstruct the zip file path with validated components
            sanitized_zip_path = str(zip_file_dir / zip_file_name)
            
            # Additional validation: ensure the path is absolute and normalized
            if not os.path.isabs(sanitized_zip_path):
                error_msg = f"ZIP file path must be absolute: {sanitized_zip_path}"
                await ctx.error(error_msg)
                return {"success": False, "error": error_msg}
            
        except (OSError, ValueError) as e:
            error_msg = f"Invalid ZIP file path: {zip_file_path} - {str(e)}"
            await ctx.error(error_msg)
            return {"success": False, "error": error_msg}
        
        # Create ZIP using subprocess with fully sanitized paths
        # SECURITY: Both paths have been extensively validated:
        # sanitized_zip_path: Path validation, filename filtering, absolute path check
        # sanitized_config_path: Path.resolve(), existence check, directory validation
        # Using array form prevents shell injection attacks
        cmd = ["zip", "-r", sanitized_zip_path, "."]
        # nosemgrep: dangerous-subprocess-use-audit
        result = subprocess.run(cmd, cwd=sanitized_config_path, capture_output=True, text=True)
        
        if result.returncode == 0:
            await ctx.info(f"Successfully created ZIP file: {zip_file_path}")
            return {"success": True, "zip_path": zip_file_path}
        else:
            error_msg = f"ZIP creation failed: {result.stderr}"
            await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "manual_commands": [
                    f"mkdir -p {expanded_path}",
                    f"cd {config_path}",
                    f"zip -r {zip_file_path} ."
                ]
            }
    except Exception as e:
        error_msg = f"Error creating ZIP: {str(e)}"
        await ctx.error(error_msg)
        return {"success": False, "error": error_msg}

async def _validate_from_docker_path(ctx: Context, docker_zip_path: str = None) -> Dict[str, Any]:
    """Validate configuration from Docker shared volume path."""
    try:
        # Use environment variable for container path if not provided
        if docker_zip_path is None:
            container_share_path = os.environ.get("LZA_CONFIG_CONTAINER_PATH", "/app/lza-config")
            docker_zip_path = os.path.join(container_share_path, "config.zip")
        
        if not os.path.exists(docker_zip_path):
            return {
                "valid": False,
                "errors": [{"message": f"ZIP file not found at {docker_zip_path}", "severity": "error"}],
                "message": "ZIP file not accessible"
            }
        
        # Extract and validate
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = os.path.join(temp_dir, "extracted_config")
            os.makedirs(config_dir, exist_ok=True)
            
            with zipfile.ZipFile(docker_zip_path, 'r') as zip_ref:
                zip_ref.extractall(config_dir)
                
            # Perform validation
            validation_result = validate_configuration_impl(config_dir)
            
            # Store the config directory path for potential S3 upload integration
            # Note: This path will be temporary and only valid during this function call
            validation_result["_temp_config_path"] = config_dir
            
            return validation_result
            
    except Exception as e:
        error_msg = f"Validation error: {str(e)}"
        await ctx.error(error_msg)
        return {
            "valid": False,
            "errors": [{"message": error_msg, "severity": "error"}],
            "message": "Validation failed"
        }

def _validate_cleanup_inputs(
    cleanup_type: str,
    path: Optional[str]
) -> Dict[str, Any]:
    """
    Validate cleanup inputs.
    
    Args:
        cleanup_type: Type of cleanup to validate ("validation_zip" or "retrieved_config")
        path: Path to validate (optional for validation_zip, required for retrieved_config)
        
    Returns:
        Dictionary with validation result and LLM-friendly error message if invalid
        
    Examples:
        >>> _validate_cleanup_inputs("validation_zip", None)
        {"valid": True}
        
        >>> _validate_cleanup_inputs("retrieved_config", "/tmp/lza-config-abc123")
        {"valid": True}
        
        >>> _validate_cleanup_inputs("invalid_type", None)
        {"valid": False, "error": "Invalid cleanup type 'invalid_type'. Please use 'validation_zip' to clean up validation files or 'retrieved_config' to clean up retrieved configuration directories."}
        
        >>> _validate_cleanup_inputs("retrieved_config", None)
        {"valid": False, "error": "The 'path' parameter is required when cleanup_type is 'retrieved_config'. Please provide the temporary directory path returned from getConfigurationFromS3."}
    """
    # Validate cleanup_type
    valid_cleanup_types = ["validation_zip", "retrieved_config"]
    if cleanup_type not in valid_cleanup_types:
        return {
            "valid": False,
            "error": f"Invalid cleanup type '{cleanup_type}'. Please use 'validation_zip' to clean up validation files or 'retrieved_config' to clean up retrieved configuration directories."
        }
    
    # Validate path requirements based on cleanup_type
    if cleanup_type == "retrieved_config" and not path:
        return {
            "valid": False,
            "error": "The 'path' parameter is required when cleanup_type is 'retrieved_config'. Please provide the temporary directory path returned from getConfigurationFromS3."
        }
    
    # All validations passed
    return {"valid": True}

async def _cleanup_zip_with_bash(ctx: Context, local_share_path: str) -> Dict[str, Any]:
    """Clean up ZIP file using bash commands."""
    try:
        expanded_path = os.path.expanduser(local_share_path)
        zip_file_path = os.path.join(expanded_path, "config.zip")
        
        if os.path.exists(zip_file_path):
            os.remove(zip_file_path)
            await ctx.info(f"Cleaned up ZIP file: {zip_file_path}")
            return {"success": True}
        else:
            await ctx.info("ZIP file already cleaned up")
            return {"success": True}
            
    except Exception as e:
        error_msg = f"Cleanup error: {str(e)}"
        await ctx.error(error_msg)
        return {"success": False, "error": error_msg}

async def cleanup_configuration(
    ctx: Context,
    cleanup_type: str,
    path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Unified cleanup for LZA configuration files and directories.
    
    Handles multiple cleanup scenarios:
    1. validation_zip: Removes config.zip from share location
    2. retrieved_config: Removes extracted configuration directory
    
    Args:
        ctx: MCP context for logging
        cleanup_type: Type of cleanup ("validation_zip" or "retrieved_config")
        path: Optional path override. For validation_zip, defaults to ~/Documents/lza-config.
              For retrieved_config, must specify the temp directory path.
        
    Returns:
        Dictionary with cleanup status
        
    Examples:
        # Clean up validation ZIP
        cleanup_configuration(ctx, cleanup_type="validation_zip")
        
        # Clean up validation ZIP from custom location
        cleanup_configuration(ctx, cleanup_type="validation_zip", path="~/custom/path")
        
        # Clean up retrieved configuration
        cleanup_configuration(ctx, cleanup_type="retrieved_config", path="/tmp/lza-config-abc123")
    """
    # Validate inputs
    validation_result = _validate_cleanup_inputs(cleanup_type, path)
    if not validation_result["valid"]:
        await ctx.error(validation_result["error"])
        return {
            "success": False,
            "error": validation_result["error"],
            "cleanup_type": cleanup_type
        }
    
    try:
        if cleanup_type == "validation_zip":
            # Handle validation ZIP cleanup
            share_path = path if path else "~/Documents/lza-config"
            expanded_path = os.path.expanduser(share_path)
            zip_file_path = os.path.join(expanded_path, "config.zip")
            
            if os.path.exists(zip_file_path):
                os.remove(zip_file_path)
                await ctx.info(f"✅ Cleaned up validation ZIP: {zip_file_path}")
                logger.info(f"Cleaned up validation ZIP file: {zip_file_path}")
                return {
                    "success": True,
                    "cleanup_type": cleanup_type,
                    "path": zip_file_path,
                    "existed": True,
                    "message": "Validation ZIP file cleaned up successfully"
                }
            else:
                await ctx.info(f"✅ Validation ZIP already cleaned up: {zip_file_path}")
                return {
                    "success": True,
                    "cleanup_type": cleanup_type,
                    "path": zip_file_path,
                    "existed": False,
                    "message": "Validation ZIP file already cleaned up"
                }
        
        elif cleanup_type == "retrieved_config":
            # Handle retrieved config directory cleanup
            import shutil
            
            # Import S3ConfigRetrieval to access tracking dicts
            from ..config.get_config_s3 import S3ConfigRetrieval
            
            if not os.path.exists(path):
                await ctx.info(f"✅ Configuration directory already cleaned up: {path}")
                return {
                    "success": True,
                    "cleanup_type": cleanup_type,
                    "path": path,
                    "existed": False,
                    "message": "Configuration directory already cleaned up"
                }
            
            # Remove the entire directory tree
            shutil.rmtree(path)
            await ctx.info(f"✅ Cleaned up configuration directory: {path}")
            logger.info(f"Cleaned up retrieved configuration directory: {path}")
            
            # Update tracking dicts if this is a tracked directory
            # Note: We need to access the singleton instance's tracking dicts
            # This is handled by creating a temporary instance to access class-level tracking
            retrieval_instance = S3ConfigRetrieval()
            if path in retrieval_instance._temp_directories:
                del retrieval_instance._temp_directories[path]
            if retrieval_instance._last_temp_directory == path:
                retrieval_instance._last_temp_directory = None
            
            # Verify directory no longer exists
            if os.path.exists(path):
                error_msg = f"Failed to remove directory: {path} still exists"
                await ctx.error(error_msg)
                logger.error(error_msg)
                return {
                    "success": False,
                    "cleanup_type": cleanup_type,
                    "path": path,
                    "error": error_msg,
                    "message": "Failed to verify directory removal"
                }
            
            return {
                "success": True,
                "cleanup_type": cleanup_type,
                "path": path,
                "existed": True,
                "message": "Configuration directory cleaned up successfully"
            }
        
    except Exception as e:
        error_msg = f"Cleanup failed: {str(e)}"
        await ctx.error(error_msg)
        logger.error(f"Cleanup error for type '{cleanup_type}': {str(e)}")
        return {
            "success": False,
            "cleanup_type": cleanup_type,
            "path": path,
            "error": error_msg,
            "troubleshooting": [
                "Check that the path is correct",
                "Verify file system permissions",
                "Ensure the file/directory is not locked by another process",
                "Check available disk space"
            ]
        }

async def _offer_s3_upload_after_validation(ctx: Context, config_path: str, validation_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Offer S3 upload after successful validation.
    
    This function integrates with the S3 upload tools to provide a seamless workflow
    transition from validation to upload. It follows requirement 1.1 and 1.2.
    
    Args:
        ctx: MCP context for logging and user interaction
        config_path: Path to the validated configuration
        validation_result: Result from the validation process
        
    Returns:
        Dictionary with upload offer result and user response
    """
    try:
        # Only offer upload if validation was successful
        if not validation_result.get("valid", False):
            await ctx.info("Validation failed - S3 upload not offered")
            return {
                "upload_offered": False,
                "reason": "validation_failed",
                "message": "S3 upload only available after successful validation"
            }
        
        # Import S3 upload functionality
        try:
            from .s3_upload_tools import S3UploadTool
        except ImportError as e:
            await ctx.error(f"S3 upload tools not available: {str(e)}")
            return {
                "upload_offered": False,
                "reason": "s3_tools_unavailable",
                "error": str(e),
                "message": "S3 upload functionality is not available"
            }
        
        # Offer S3 upload to user
        await ctx.info("🎉 Configuration validation completed successfully!")
        await ctx.info("📤 Would you like to upload this validated configuration to S3?")
        await ctx.info("   This will prepare the configuration for deployment through the LZA pipeline.")
        
        # In a real implementation, this would prompt the user for input
        # For now, we'll simulate user acceptance for integration testing
        user_accepts_upload = True  # This would be replaced with actual user input
        
        if not user_accepts_upload:
            await ctx.info("S3 upload declined by user")
            return {
                "upload_offered": True,
                "user_accepted": False,
                "message": "User declined S3 upload"
            }
        
        # User accepted - proceed with S3 upload
        await ctx.info("User accepted S3 upload - initiating upload process...")
        
        # Initialize S3 upload tool
        s3_tool = S3UploadTool()
        
        # Upload configuration using the validated config path
        upload_result = await s3_tool.upload_configuration(
            ctx=ctx,
            config_path=config_path,
            bucket_name=None,  # Use default bucket determination
            offer_pipeline_release=True
        )
        
        # Combine validation and upload results
        return {
            "upload_offered": True,
            "user_accepted": True,
            "upload_result": upload_result,
            "message": "S3 upload process completed",
            "validation_result": validation_result
        }
        
    except Exception as e:
        error_message = f"Error offering S3 upload: {str(e)}"
        await ctx.error(error_message)
        return {
            "upload_offered": True,
            "user_accepted": True,
            "upload_result": {
                "success": False,
                "error": str(e),
                "message": error_message
            },
            "error": str(e)
        }

async def _offer_s3_upload_after_validation(ctx: Context, config_path: str, validation_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Offer S3 upload to the user after successful validation.
    
    This function provides a user prompt to upload the validated configuration to S3
    and optionally release the pipeline for deployment.
    
    Args:
        ctx: MCP context for logging and user interaction
        config_path: Path to the validated configuration
        validation_result: Result from the validation process
        
    Returns:
        Upload offer result with user decision and next steps
    """
    try:
        await ctx.info("🎉 Configuration validation completed successfully!")
        await ctx.info("")
        await ctx.info("📤 Next Step: Upload Configuration to S3")
        await ctx.info("Your validated configuration is ready to be uploaded to S3 for deployment.")
        await ctx.info("")
        await ctx.info("To upload your configuration, use:")
        await ctx.info("  • uploadConfigurationToS3 - Automatically detects validation ZIP and uploads")
        await ctx.info("  • uploadConfigurationToS3WithCustomBucket - Use a specific bucket name")
        await ctx.info("")
        await ctx.info("After upload, you can release the pipeline with:")
        await ctx.info("  • releasePipeline - Starts the LZA deployment pipeline")
        await ctx.info("")
        await ctx.info("💡 Tip: uploadConfigurationToS3 will automatically find and use your validation ZIP.")
        
        return {
            "upload_offered": True,
            "user_prompted": True,
            "config_path": config_path,
            "validation_result": validation_result,
            "next_steps": [
                "Use uploadConfigurationToS3 (automatically detects validation ZIP)",
                "Or use uploadConfigurationToS3WithCustomBucket for custom bucket",
                "Then use releasePipeline to deploy"
            ],
            "message": "S3 upload tools are available for deployment"
        }
        
    except Exception as e:
        error_message = f"Failed to offer S3 upload: {str(e)}"
        await ctx.error(error_message)
        
        return {
            "upload_offered": False,
            "error": str(e),
            "message": error_message
        }

async def _integrate_s3_upload_workflow(ctx: Context, config_path: str, validation_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Integrate S3 upload workflow with validation results.
    
    This function provides seamless workflow transition from validation to upload
    as specified in requirements 1.1 and 1.2.
    
    Args:
        ctx: MCP context for logging and user interaction
        config_path: Path to the validated configuration
        validation_result: Result from the validation process
        
    Returns:
        Combined validation and upload workflow result
    """
    try:
        # Start with validation result
        workflow_result = {
            "validation": validation_result,
            "s3_upload_integration": {
                "available": True,
                "offered": False,
                "completed": False
            }
        }
        
        # Only proceed if validation was successful
        if not validation_result.get("valid", False):
            workflow_result["s3_upload_integration"]["available"] = False
            workflow_result["s3_upload_integration"]["reason"] = "validation_failed"
            return workflow_result
        
        # Offer S3 upload after successful validation
        upload_offer_result = await _offer_s3_upload_after_validation(ctx, config_path, validation_result)
        
        # Update workflow result with upload offer outcome
        workflow_result["s3_upload_integration"].update({
            "offered": upload_offer_result.get("upload_offered", False),
            "user_prompted": upload_offer_result.get("user_prompted", False),
            "next_steps": upload_offer_result.get("next_steps", []),
            "message": upload_offer_result.get("message", "")
        })
        
        # Add any errors from the upload process
        if "error" in upload_offer_result:
            workflow_result["s3_upload_integration"]["error"] = upload_offer_result["error"]
        
        return workflow_result
        
    except Exception as e:
        error_message = f"S3 upload workflow integration failed: {str(e)}"
        await ctx.error(error_message)
        
        return {
            "validation": validation_result,
            "s3_upload_integration": {
                "available": False,
                "offered": False,
                "completed": False,
                "error": str(e),
                "message": error_message
            }
        }

def register_validation_tools(mcp):
    """Register validation-related MCP tools."""
    
    @mcp.tool(name="validateConfigurationFromS3") # nosemgrep: useless-inner-function
    async def validate_configuration_from_s3(
        ctx: Context,
        s3_path: str,
    ) -> Dict[str, Any]:
        """Validate LZA configuration files stored in an S3 bucket.
        
        ⚠️ IMPORTANT FOR LLM: ALWAYS offer validation method choice to users first!
        
        BEFORE using this tool, present these validation options to the user:
        
        1. **S3-based validation** (this tool): Most reliable, uses cloud storage
           - Requires AWS credentials and S3 bucket
           - User uploads ZIP file to S3, then validates
           
        2. **Local shared volume validation**: Uses Docker shared volumes
           - Requires Docker with shared volume mount
           - Creates ZIP locally and validates via shared volume
        
        Ask: "Which validation method would you prefer? (1 or 2)"
        Only proceed with S3 validation if user chooses option 1.
        
        This tool is part of the S3 validation workflow:
        1. checkAwsConnectivity() - Verify AWS credentials
        2. Ensure S3 bucket exists (ask user for bucket name or help them create one)
        3. User uploads configuration ZIP to S3
        4. validateConfigurationFromS3() - This tool validates the configuration
        
        The tool will:
        - Download the ZIP file from S3 to the Docker container
        - Extract all files maintaining directory structure
        - Run the official LZA validator against the configuration
        - Provide detailed error reporting and troubleshooting guidance
        
        ⚠️ CRITICAL: The ZIP file must contain the ENTIRE configuration directory structure,
        including all subdirectories and supporting files (IAM policies, SCP policies, etc.).
        Use: `cd /path/to/config && zip -r config.zip .` (note the dot at the end)
        
        Args:
            s3_path (str): S3 path to the ZIP file containing LZA configuration files. Format: s3://bucket-name/path/to/file.zip or bucket-name/path/to/file.zip
            
        Returns:
            Dictionary with validation results including success status, detailed errors, diagnostics, and troubleshooting guidance
        """
        # Check if the path looks like a local file path instead of S3
        if s3_path.startswith('/') or ':\\' in s3_path:
            error_message = "ERROR: Local file paths cannot be used for validation. Docker containers cannot access the local filesystem."
            await ctx.error(error_message)
            return {
                "valid": False,
                "errors": [{"message": error_message, "severity": "error"}],
                "message": "Local file paths are not supported",
                "workflow_correction": """
CRITICAL WORKFLOW ERROR: You are trying to use a local file path for validation.
The Docker container CANNOT access files on the local filesystem.

Please follow the complete workflow:
1. Call checkAwsConnectivity() to verify AWS credentials
2. Ask the user if they have an existing S3 bucket or help them create one using AWS CLI:
   aws s3 mb s3://your-bucket-name --region your-region
3. Help the user upload their configuration to S3:
   cd /path/to/config && zip -r config.zip .
   aws s3 cp config.zip s3://your-bucket-name/config.zip
4. Use validateConfigurationFromS3() with the S3 path
"""
            }
        
        # Parse the S3 path
        try:
            if s3_path.startswith('s3://'):
                s3_path = s3_path[5:]  # Remove 's3://' prefix
                
            parts = s3_path.split('/', 1)
            if len(parts) < 2:
                await ctx.error("Invalid S3 path format. Expected 's3://bucket-name/path/to/file.zip'")
                return {
                    "valid": False,
                    "errors": [{"message": "Invalid S3 path format", "severity": "error"}],
                    "message": "Invalid S3 path format"
                }
            
            bucket_name = parts[0]
            key = parts[1]
            
            await ctx.info(f"Validating configuration from S3 path: s3://{bucket_name}/{key}")
            
            # Download the ZIP file to a temporary location
            with tempfile.TemporaryDirectory() as temp_dir:
                zip_path = os.path.join(temp_dir, "config.zip")
                
                # Download the file from S3
                await ctx.info(f"Downloading configuration ZIP from S3")
                
                if not download_from_s3(bucket_name, key, zip_path):
                    await ctx.error(f"Failed to download ZIP file from S3")
                    return {
                        "valid": False,
                        "errors": [{"message": f"Failed to download ZIP file from S3: s3://{bucket_name}/{key}", "severity": "error"}],
                        "message": "S3 download failed"
                    }
                    
                # Check if the file is a valid ZIP
                if not zipfile.is_zipfile(zip_path):
                    await ctx.error("The downloaded file is not a valid ZIP archive")
                    return {
                        "valid": False,
                        "errors": [{"message": "The downloaded file is not a valid ZIP archive", "severity": "error"}],
                        "message": "Invalid ZIP file"
                    }
                
                # Extract the ZIP file to a new temporary directory
                config_dir = os.path.join(temp_dir, "extracted_config")
                os.makedirs(config_dir, exist_ok=True)
                
                await ctx.info(f"Extracting ZIP file")
                try:
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(config_dir)
                        
                        # List extracted files for logging
                        extracted_files = [f.filename for f in zip_ref.infolist() 
                                          if not f.filename.endswith('/')]  # Skip directories
                        await ctx.info(f"Extracted {len(extracted_files)} files from ZIP")
                        
                        # Count total files and directories after extraction
                        total_files = sum([len(files) for _, _, files in os.walk(config_dir)])
                        total_dirs = sum([len(dirs) for _, dirs, _ in os.walk(config_dir)])
                        await ctx.info(f"Total extracted: {total_files} files in {total_dirs} directories")
                        
                        # Now validate the configuration
                        await ctx.info(f"Validating configuration from extracted directory")
                        result = validate_configuration_impl(config_dir)
                        
                        # Add detailed results for missing files
                        if not result["valid"] and "missing_files" in result:
                            if result["missing_files"] and len(result["missing_files"]) > 0:
                                missing_files_advice = """
## Important: Missing Files Detected

Your ZIP file is missing some required files. Please make sure you:

1. Used `zip -r config.zip .` to include ALL files and subdirectories
2. Included all referenced JSON files in the proper subdirectories
3. Double-check that your configuration references valid file paths

When you create the ZIP file, make sure you're in the root directory of your LZA configuration
and include ALL files, not just the YAML files.
"""
                                if "diagnostics" in result:
                                    result["diagnostics"] = missing_files_advice + "\n\n" + result["diagnostics"]
                        
                        # Integrate S3 upload workflow after successful validation
                        # Only integrate if validation was successful to maintain backward compatibility
                        if result.get("valid", False):
                            workflow_result = await _integrate_s3_upload_workflow(ctx, config_dir, result)
                            
                            # Preserve the original validation result structure and add S3 integration info
                            result["s3_upload_integration"] = workflow_result.get("s3_upload_integration", {})
                        
                        return result
                        
                except zipfile.BadZipFile:
                    await ctx.error("ZIP file is corrupted or invalid")
                    return {
                        "valid": False,
                        "errors": [{"message": "ZIP file is corrupted or invalid", "severity": "error"}],
                        "message": "Invalid ZIP file"
                    }
                except Exception as e:
                    await ctx.error(f"Error processing ZIP file: {str(e)}")
                    return {
                        "valid": False,
                        "errors": [{"message": f"Error processing ZIP file: {str(e)}", "severity": "error"}],
                        "message": "ZIP processing error"
                    }
                    
        except Exception as e:
            await ctx.error(f"Error during S3 validation: {str(e)}")
            return {
                "valid": False,
                "errors": [{"message": f"Error during S3 validation: {str(e)}", "severity": "error"}],
                "message": "Validation error"
            }

    @mcp.tool(name="validateConfigurationFromShare") # nosemgrep: useless-inner-function
    async def validate_configuration_from_share(
        ctx: Context,
        local_share_path: str = "~/Documents/lza-config"
    ) -> Dict[str, Any]:
        """Complete LZA validation workflow using Docker shared volume.
        
        ⚠️ IMPORTANT FOR LLM: ALWAYS offer validation method choice to users first!
        
        BEFORE using this tool, present these validation options to the user:
        
        1. **S3-based validation**: Most reliable, uses cloud storage
           - Requires AWS credentials and S3 bucket
           - User uploads ZIP file to S3, then validates
           
        2. **Local shared volume validation** (this tool): Uses Docker shared volumes
           - Requires Docker with shared volume mount
           - Creates ZIP locally and validates via shared volume
        
        Ask: "Which validation method would you prefer? (1 or 2)"
        Only proceed with shared volume validation if user chooses option 2.
        
        ⚠️ CRITICAL FOR LLM: DO NOT RUN DOCKER COMMANDS DIRECTLY! Use MCP tools only.
        
        IMPORTANT INSTRUCTIONS FOR LLM: This tool requires you to execute the following steps IN ORDER:
        
        1. **Check AWS Connectivity**: 
           - First call checkAwsConnectivity() to verify AWS credentials
           - Do not proceed if AWS connectivity fails
        
        2. **Find Available LZA Configurations**:
           - Search the workspace for directories containing both 'accounts-config.yaml' and 'organization-config.yaml'
           - Present discovered configurations to the user as a numbered list
           - Ask the user to select which configuration to validate
        
        3. **Create ZIP and Place in Docker Share Location**:
           - Create a ZIP file of the ENTIRE selected configuration directory
           - CRITICAL: Include ALL files and subdirectories, even empty ones
           - Use commands like: cd /path/to/selected/config && zip -r ~/Documents/lza-config/config.zip .
           - The dot (.) at the end is MANDATORY - it includes all files and preserves directory structure
        
        4. **Run Validation**:
           - Call validateConfigurationFromShare() MCP tool to perform validation
           - DO NOT run Docker commands directly - use the MCP tool instead
           - The MCP server will handle Docker container execution internally
        
        5. **Offer S3 Upload**:
           - After successful validation, preserve the ZIP file for S3 upload
           - Inform user that uploadConfigurationFromShare is available
           - Ask if they want to upload the validated configuration to S3
           - Do NOT remove the ZIP file - it's needed for deployment
           - Ensure the share location is clean for future use
        
        WORKFLOW REQUIREMENTS:
        - Docker container must be run with shared volume mount: -v "~/Documents/lza-config:/app/lza-config"
        - ZIP file must contain ALL files and subdirectories, not just YAML files
        - Use `cd /path/to/config && zip -r ~/Documents/lza-config/config.zip .` (dot is mandatory)
        - Empty directories and hidden files must be preserved in the ZIP
        - IMPORTANT: Do NOT clean up ZIP file - preserve it for S3 upload workflow
        
        ⚠️ MCP TOOL USAGE - CRITICAL:
        - Step 4 must use validateConfigurationFromShare() MCP tool
        - DO NOT execute Docker run commands directly
        - DO NOT use execute_bash to run Docker containers
        - The MCP server handles Docker execution internally
        
        Args:
            local_share_path (str, optional): Path on local system for shared files (default: ~/Documents/lza-config)
            workspace_path (str, optional): Path to search for LZA configurations (default: current directory)
            
        Returns:
            Complete validation results with workflow status tracking for each step
            
        Example LLM Workflow:
        ```
        1. "Let me check your AWS connectivity first..."
           → Use MCP tool: checkAwsConnectivity()
        
        2. "I'll search for LZA configurations in your workspace..."
           → Search for directories with accounts-config.yaml and organization-config.yaml
           → Present: "Found 2 LZA configurations: 1. /path/to/config1  2. /path/to/config2"
           → Ask: "Which configuration would you like to validate? (1 or 2)"
        
        3. "I'll create a ZIP file and place it in the Docker share location..."
           → Use bash: cd /selected/path && zip -r ~/Documents/lza-config/config.zip .
           → Confirm: "ZIP file created successfully"
        
        4. "Now I'll run the validation using the MCP tool..."
           → Use MCP tool: validateConfigurationFromShare()
           → ⚠️ DO NOT run Docker commands - the MCP tool handles this internally
        
        5. "Configuration ready for S3 upload..."
           → Inform user: "ZIP file preserved for upload - use uploadConfigurationFromShare"
           → Offer: "Would you like to upload to S3 for deployment?"
        ```
        
        ⚠️ REMEMBER: Step 3 uses bash commands for ZIP creation. Step 4 uses the MCP tool. Step 5 preserves ZIP for upload!
        ⚠️ CRITICAL: The ZIP command MUST use the dot (.) and be run from within the config directory!
        """
        # Initialize workflow tracking
        workflow_status = {
            "discovered_configs": [],
            "selected_config": None,
            "zip_created": False,
            "zip_cleaned": False,
            "steps_completed": []
        }
        
        try:
            # Step 1: Validate AWS Credentials
            await ctx.info("🔐 Step 1: Validating AWS credentials...")
            try:
                session = get_aws_session()
                sts_client = session.client('sts')
                caller_identity = sts_client.get_caller_identity()
                await ctx.info(f"✅ AWS credentials valid - Account: {caller_identity['Account']}")
                workflow_status["steps_completed"].append("credentials_validated")
            except Exception as e:
                await ctx.error(f"❌ AWS credentials validation failed: {str(e)}")
                return {
                    "valid": False,
                    "errors": [{"message": f"AWS credentials validation failed: {str(e)}", "severity": "error"}],
                    "message": "AWS connectivity required for LZA validation",
                    **workflow_status,
                    "troubleshooting": "Please ensure AWS credentials are properly configured"
                }
            
            # Step 2: Check for ZIP file in shared volume
            await ctx.info("📦 Step 2: Checking for config.zip in shared volume...")
            container_share_path = os.environ.get("LZA_CONFIG_CONTAINER_PATH", "/app/lza-config")
            docker_zip_path = os.path.join(container_share_path, "config.zip")
            
            if not os.path.exists(docker_zip_path):
                expanded_local_path = os.path.expanduser(local_share_path)
                return {
                    "valid": False,
                    "errors": [{"message": f"config.zip not found in shared volume at {docker_zip_path}", "severity": "error"}],
                    "message": "ZIP file not found in shared volume",
                    **workflow_status,
                    "instructions": f"""
PREREQUISITE STEPS MISSING:

Before calling this tool, you must:

1. Create a ZIP file of your LZA configuration:
   cd /path/to/your/lza-config
   zip -r config.zip .

2. Place the ZIP file in the shared volume location:
   cp config.zip {expanded_local_path}/

3. Ensure Docker is running with shared volume mount:
   docker run -v "{expanded_local_path}:{container_share_path}" ...

The ZIP file should be accessible at: {docker_zip_path}
"""
                }
            
            # Step 3: Run validation on shared ZIP file
            await ctx.info("⚖️  Step 3: Running validation...")
            validation_result = await _validate_from_docker_path(ctx, docker_zip_path)
            
            # Add workflow tracking to results
            validation_result.update(workflow_status)
            validation_result["steps_completed"].append("validation_completed")
            
            # Step 4: Integrate S3 upload workflow after validation
            if validation_result.get("valid", False):
                # Success message will be shown by _integrate_s3_upload_workflow
                
                # Extract config path from the ZIP for S3 upload integration
                # We'll use a temporary directory to extract and get the config path
                with tempfile.TemporaryDirectory() as temp_extract_dir:
                    config_extract_path = os.path.join(temp_extract_dir, "config")
                    os.makedirs(config_extract_path, exist_ok=True)
                    
                    # Extract ZIP to get config path for S3 upload
                    with zipfile.ZipFile(docker_zip_path, 'r') as zip_ref:
                        zip_ref.extractall(config_extract_path)
                    
                    # Integrate S3 upload workflow
                    workflow_result = await _integrate_s3_upload_workflow(ctx, config_extract_path, validation_result)
                    
                    # Preserve original validation result structure and add S3 integration info
                    validation_result["s3_upload_integration"] = workflow_result.get("s3_upload_integration", {})
                    validation_result.update(workflow_status)
                    validation_result["steps_completed"].append("s3_upload_integration_completed")
                    
                    # Success message handled by _integrate_s3_upload_workflow
                    return validation_result
            else:
                await ctx.info("❌ Validation completed with errors - S3 upload not offered")
                return validation_result
            
        except Exception as e:
            await ctx.error(f"Unexpected error in validation workflow: {str(e)}")
            return {
                "valid": False,
                "errors": [{"message": f"Workflow error: {str(e)}", "severity": "error"}],
                "message": "Unexpected workflow error",
                **workflow_status
            }



    @mcp.tool(name="cleanupConfiguration") # nosemgrep: useless-inner-function
    async def cleanup_configuration_tool(
        ctx: Context,
        cleanup_type: str,
        path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Clean up LZA configuration files and directories.
        
        This tool handles multiple cleanup scenarios:
        1. "validation_zip": Removes config.zip from validation share location
        2. "retrieved_config": Removes extracted configuration directory from S3 retrieval
        
        Args:
            cleanup_type: Type of cleanup to perform ("validation_zip" or "retrieved_config")
            path: Optional path override. For validation_zip, defaults to ~/Documents/lza-config.
                  For retrieved_config, must specify the temp directory path.
            
        Returns:
            Dictionary with cleanup status
            
        Examples:
            # Clean up validation ZIP
            cleanup_configuration(ctx, cleanup_type="validation_zip")
            
            # Clean up validation ZIP from custom location
            cleanup_configuration(ctx, cleanup_type="validation_zip", path="~/custom/path")
            
            # Clean up retrieved configuration
            cleanup_configuration(ctx, cleanup_type="retrieved_config", path="/tmp/lza-config-abc123")
        """
        await ctx.info(f"🧹 Cleaning up {cleanup_type}...")
        result = await cleanup_configuration(ctx, cleanup_type, path)
        return result

    logger.info("Validation tools registered successfully")