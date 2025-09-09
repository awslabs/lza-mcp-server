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
import os
import tempfile
import zipfile
from typing import Dict, Any

from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.aws_access import download_from_s3
from awslabs.lza_mcp_server.tools.validation.common import validate_configuration_impl

logger = logging.getLogger(__name__)


async def _offer_s3_upload_after_validation(
    ctx: Context, config_path: str, validation_result: Dict[str, Any]
) -> Dict[str, Any]:
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
        await ctx.info(
            "Your validated configuration is ready to be uploaded to S3 for deployment."
        )
        await ctx.info("")
        await ctx.info("To upload your configuration, use:")
        await ctx.info(
            "  • uploadConfigurationToS3 - Automatically detects validation ZIP and uploads"
        )
        await ctx.info(
            "  • uploadConfigurationToS3(bucket_name='custom-bucket') - Use a specific bucket name"
        )
        await ctx.info("")
        await ctx.info("After upload, you can release the pipeline with:")
        await ctx.info(
            "  • releasePipelineAfterUpload - Starts the LZA deployment pipeline"
        )
        await ctx.info("")
        await ctx.info(
            "💡 Tip: uploadConfigurationToS3 will automatically find and use your validation ZIP."
        )

        return {
            "upload_offered": True,
            "user_prompted": True,
            "config_path": config_path,
            "validation_result": validation_result,
            "next_steps": [
                "Use uploadConfigurationToS3 (automatically detects validation ZIP)",
                "Or use uploadConfigurationToS3(bucket_name='custom-bucket') for custom bucket",
                "Then use releasePipelineAfterUpload to deploy",
            ],
            "message": "S3 upload tools are available for deployment",
        }

    except Exception as e:
        error_message = f"Failed to offer S3 upload: {str(e)}"
        await ctx.error(error_message)

        return {"upload_offered": False, "error": str(e), "message": error_message}


async def _integrate_s3_upload_workflow(
    ctx: Context, config_path: str, validation_result: Dict[str, Any]
) -> Dict[str, Any]:
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
                "completed": False,
            },
        }

        # Only proceed if validation was successful
        if not validation_result.get("valid", False):
            workflow_result["s3_upload_integration"]["available"] = False
            workflow_result["s3_upload_integration"]["reason"] = "validation_failed"
            return workflow_result

        # Offer S3 upload after successful validation
        upload_offer_result = await _offer_s3_upload_after_validation(
            ctx, config_path, validation_result
        )

        # Update workflow result with upload offer outcome
        workflow_result["s3_upload_integration"].update(
            {
                "offered": upload_offer_result.get("upload_offered", False),
                "user_prompted": upload_offer_result.get("user_prompted", False),
                "next_steps": upload_offer_result.get("next_steps", []),
                "message": upload_offer_result.get("message", ""),
            }
        )

        # Add any errors from the upload process
        if "error" in upload_offer_result:
            workflow_result["s3_upload_integration"]["error"] = upload_offer_result[
                "error"
            ]

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
                "message": error_message,
            },
        }


async def tool_validate_configuration_from_s3(
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
    2. setupS3Bucket() - Create/verify S3 bucket
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
    if s3_path.startswith("/") or ":\\" in s3_path:
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
2. Call setupS3Bucket() to create/verify an S3 bucket
3. Help the user upload their configuration to S3
4. Use validateConfigurationFromS3() with the S3 path
""",
        }

    # Parse the S3 path
    try:
        if s3_path.startswith("s3://"):
            s3_path = s3_path[5:]  # Remove 's3://' prefix

        parts = s3_path.split("/", 1)
        if len(parts) < 2:
            await ctx.error(
                "Invalid S3 path format. Expected 's3://bucket-name/path/to/file.zip'"
            )
            return {
                "valid": False,
                "errors": [{"message": "Invalid S3 path format", "severity": "error"}],
                "message": "Invalid S3 path format",
            }

        bucket_name = parts[0]
        key = parts[1]

        await ctx.info(
            f"Validating configuration from S3 path: s3://{bucket_name}/{key}"
        )

        # Download the ZIP file to a temporary location
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, "config.zip")

            # Download the file from S3
            await ctx.info("Downloading configuration ZIP from S3")

            if not download_from_s3(bucket_name, key, zip_path):
                await ctx.error("Failed to download ZIP file from S3")
                return {
                    "valid": False,
                    "errors": [
                        {
                            "message": f"Failed to download ZIP file from S3: s3://{bucket_name}/{key}",
                            "severity": "error",
                        }
                    ],
                    "message": "S3 download failed",
                }

            # Check if the file is a valid ZIP
            if not zipfile.is_zipfile(zip_path):
                await ctx.error("The downloaded file is not a valid ZIP archive")
                return {
                    "valid": False,
                    "errors": [
                        {
                            "message": "The downloaded file is not a valid ZIP archive",
                            "severity": "error",
                        }
                    ],
                    "message": "Invalid ZIP file",
                }

            # Extract the ZIP file to a new temporary directory
            config_dir = os.path.join(temp_dir, "extracted_config")
            os.makedirs(config_dir, exist_ok=True)

            await ctx.info("Extracting ZIP file")
            try:
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(config_dir)

                    # List extracted files for logging
                    extracted_files = [
                        f.filename
                        for f in zip_ref.infolist()
                        if not f.filename.endswith("/")
                    ]  # Skip directories
                    await ctx.info(f"Extracted {len(extracted_files)} files from ZIP")

                    # Count total files and directories after extraction
                    total_files = sum(
                        [len(files) for _, _, files in os.walk(config_dir)]
                    )
                    total_dirs = sum([len(dirs) for _, dirs, _ in os.walk(config_dir)])
                    await ctx.info(
                        f"Total extracted: {total_files} files in {total_dirs} directories"
                    )

                    # Now validate the configuration
                    await ctx.info("Validating configuration from extracted directory")
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
                                result["diagnostics"] = (
                                    missing_files_advice
                                    + "\n\n"
                                    + result["diagnostics"]
                                )

                    # Integrate S3 upload workflow after successful validation
                    # Only integrate if validation was successful to maintain backward compatibility
                    if result.get("valid", False):
                        workflow_result = await _integrate_s3_upload_workflow(
                            ctx, config_dir, result
                        )

                        # Preserve the original validation result structure and add S3 integration info
                        result["s3_upload_integration"] = workflow_result.get(
                            "s3_upload_integration", {}
                        )

                    return result

            except zipfile.BadZipFile:
                await ctx.error("ZIP file is corrupted or invalid")
                return {
                    "valid": False,
                    "errors": [
                        {
                            "message": "ZIP file is corrupted or invalid",
                            "severity": "error",
                        }
                    ],
                    "message": "Invalid ZIP file",
                }
            except Exception as e:
                await ctx.error(f"Error processing ZIP file: {str(e)}")
                return {
                    "valid": False,
                    "errors": [
                        {
                            "message": f"Error processing ZIP file: {str(e)}",
                            "severity": "error",
                        }
                    ],
                    "message": "ZIP processing error",
                }

    except Exception as e:
        await ctx.error(f"Error during S3 validation: {str(e)}")
        return {
            "valid": False,
            "errors": [
                {
                    "message": f"Error during S3 validation: {str(e)}",
                    "severity": "error",
                }
            ],
            "message": "Validation error",
        }
