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

"""Copy UC configuration from session directory to LZA configuration directory."""

import logging
import shutil
from pathlib import Path
from typing import Dict, Any

from mcp.server.fastmcp import Context

from awslabs.lza_mcp_server.error_categories import ErrorCategory
from .common import (
    get_extracted_lza_config_path,
    create_error_response,
    create_success_response,
    categorize_uc_merge_error,
)
from .session_manager import SessionManager

logger = logging.getLogger(__name__)


async def copy_uc_to_lza_config(
    ctx: Context,
    session_id: str
) -> Dict[str, Any]:
    """Copy UC configuration from session directory to extracted LZA configuration directory.
    
    This tool merges UC files with the existing LZA configuration by copying all
    files from the session directory to the LZA configuration directory. Files are
    overwritten as needed, and directory structure is preserved.
    
    After this operation completes, call uploadConfigurationToS3() WITHOUT any path
    parameter to upload the merged configuration.
    
    Args:
        ctx: MCP context for logging
        session_id: Session identifier from start_uc_merge_session()
        
    Returns:
        Dictionary with copy operation results:
        {
            "success": bool,
            "session_id": str,
            "files_copied": int,
            "directories_created": int,
            "source": str,
            "destination": str,
            "next_steps": str
        }
    """
    try:
        await ctx.info(f"Copying UC configuration from session {session_id} to LZA config")
        
        # Validate session_id is provided
        if not session_id:
            return create_error_response(
                error_message="Session ID is required",
                error_code="MISSING_SESSION_ID",
                category=ErrorCategory.VALIDATION,
                troubleshooting=[
                    "Provide a session_id parameter",
                    "Start a new session with start_uc_merge_session()",
                    "Ensure you have the session_id from the session creation response"
                ],
                next_steps="Call start_uc_merge_session() to create a session first."
            )
        
        # Validate session exists
        session_manager = SessionManager()
        is_valid, error_message = session_manager.validate_session(session_id)
        
        if not is_valid:
            return create_error_response(
                error_message=error_message,
                error_code="INVALID_SESSION",
                category=ErrorCategory.VALIDATION,
                troubleshooting=[
                    "Verify the session_id is correct",
                    "Start a new session with start_uc_merge_session()",
                    "Check that the session has not been cleaned up",
                    "Ensure the session was created successfully"
                ],
                context={"session_id": session_id},
                next_steps="Start a new session with start_uc_merge_session() and use the returned session_id."
            )
        
        # Get session directory
        session_path = session_manager.get_session_path(session_id)
        
        # Get extracted LZA config path
        lza_config_path = get_extracted_lza_config_path()
        
        if lza_config_path is None:
            return create_error_response(
                error_message="LZA configuration directory not found",
                error_code="LZA_CONFIG_NOT_FOUND",
                category=ErrorCategory.VALIDATION,
                troubleshooting=[
                    "Call getConfigurationFromS3() first to retrieve the LZA configuration",
                    "Ensure getConfigurationFromS3() completed successfully",
                    "Verify the extracted configuration path was set correctly"
                ],
                context={"session_id": session_id},
                next_steps="Call getConfigurationFromS3() to retrieve the LZA configuration first."
            )
        
        # Verify LZA config directory exists
        if not lza_config_path.exists():
            return create_error_response(
                error_message=f"LZA configuration directory does not exist: {lza_config_path}",
                error_code="LZA_CONFIG_NOT_FOUND",
                category=ErrorCategory.FILE_NOT_FOUND,
                troubleshooting=[
                    "Call getConfigurationFromS3() to retrieve the LZA configuration",
                    "Verify the configuration was extracted successfully",
                    "Check that the directory was not deleted"
                ],
                context={
                    "session_id": session_id,
                    "lza_config_path": str(lza_config_path)
                },
                next_steps="Call getConfigurationFromS3() to retrieve the LZA configuration."
            )
        
        # Verify session directory exists and has files
        if not session_path.exists():
            return create_error_response(
                error_message=f"Session directory does not exist: {session_path}",
                error_code="SESSION_NOT_FOUND",
                category=ErrorCategory.FILE_NOT_FOUND,
                troubleshooting=[
                    "Verify the session_id is correct",
                    "Check that the session has not been cleaned up",
                    "Start a new session with start_uc_merge_session()"
                ],
                context={
                    "session_id": session_id,
                    "session_path": str(session_path)
                },
                next_steps="Start a new session with start_uc_merge_session()."
            )
        
        # Count files and directories before copying
        files_copied = 0
        directories_created = 0
        
        await ctx.info(f"Copying files from {session_path} to {lza_config_path}")
        
        # Copy all files from session to LZA config, preserving structure
        try:
            for item in session_path.rglob("*"):
                # Skip metadata files
                if item.name == ".session_metadata.json":
                    continue
                
                # Calculate relative path
                relative_path = item.relative_to(session_path)
                dest_path = lza_config_path / relative_path
                
                if item.is_dir():
                    # Create directory if it doesn't exist
                    if not dest_path.exists():
                        dest_path.mkdir(parents=True, exist_ok=True)
                        directories_created += 1
                        await ctx.info(f"Created directory: {relative_path}")
                elif item.is_file():
                    # Ensure parent directory exists
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Copy file (overwrite if exists)
                    shutil.copy2(item, dest_path)
                    files_copied += 1
                    
                    if files_copied % 10 == 0:
                        await ctx.info(f"Copied {files_copied} files...")
            
            await ctx.info(
                f"Successfully copied {files_copied} files and created "
                f"{directories_created} directories from session {session_id}"
            )
            
            # Clean up session directory after successful merge
            # The UC configuration has been merged into LZA config, so session is no longer needed
            try:
                await ctx.info(f"Cleaning up session directory: {session_id}")
                shutil.rmtree(session_path)
                logger.info(f"Cleaned up session directory: {session_path}")
                await ctx.info(f"Session directory removed: {session_id}")
            except Exception as cleanup_error:
                # Log warning but don't fail the operation
                logger.warning(f"Failed to clean up session directory {session_id}: {str(cleanup_error)}")
                await ctx.warning(f"Could not remove session directory (non-critical): {str(cleanup_error)}")
            
            return create_success_response(
                data={
                    "session_id": session_id,
                    "files_copied": files_copied,
                    "directories_created": directories_created,
                    "source": str(session_path),
                    "destination": str(lza_config_path),
                    "session_cleaned_up": not session_path.exists(),
                },
                next_steps=(
                    "UC configuration merged successfully. Session directory has been cleaned up. "
                    "Call uploadConfigurationToS3() WITHOUT any path parameter "
                    "to upload the merged configuration."
                )
            )
            
        except PermissionError as e:
            return create_error_response(
                error_message=f"Permission denied during copy operation: {str(e)}",
                error_code="ACCESS_DENIED",
                category=ErrorCategory.FILE_OPERATION,
                troubleshooting=[
                    "Check file system permissions",
                    "Ensure the user has write access to the LZA configuration directory",
                    "Verify no files are locked by another process",
                    "Check container permissions and volume mounts"
                ],
                context={
                    "session_id": session_id,
                    "source": str(session_path),
                    "destination": str(lza_config_path),
                    "files_copied": files_copied,
                    "directories_created": directories_created
                },
                next_steps="Check file permissions and retry the operation."
            )
        except OSError as e:
            return create_error_response(
                error_message=f"File system error during copy operation: {str(e)}",
                error_code="FILE_OPERATION_ERROR",
                category=ErrorCategory.FILE_OPERATION,
                troubleshooting=[
                    "Check available disk space",
                    "Verify file system is not read-only",
                    "Ensure no files are corrupted",
                    "Check system logs for more details"
                ],
                context={
                    "session_id": session_id,
                    "source": str(session_path),
                    "destination": str(lza_config_path),
                    "files_copied": files_copied,
                    "directories_created": directories_created,
                    "error_type": type(e).__name__
                },
                next_steps="Check the error details and retry the operation."
            )
        except Exception as e:
            error_info = categorize_uc_merge_error(e)
            return create_error_response(
                error_message=f"Failed to copy files: {str(e)}",
                error_code=error_info["error_code"],
                category=error_info["category"],
                troubleshooting=error_info["troubleshooting"],
                context={
                    "session_id": session_id,
                    "source": str(session_path),
                    "destination": str(lza_config_path),
                    "files_copied": files_copied,
                    "directories_created": directories_created,
                    "error_type": type(e).__name__
                },
                next_steps="Check the error details and retry the operation."
            )
            
    except Exception as e:
        logger.error(f"Unexpected error copying UC to LZA config: {str(e)}")
        return create_error_response(
            error_message=f"Unexpected error during copy operation: {str(e)}",
            error_code="UNEXPECTED_ERROR",
            category=ErrorCategory.FILE_OPERATION,
            troubleshooting=[
                "Check system logs for more details",
                "Verify both session and LZA config directories are accessible",
                "Ensure sufficient system resources",
                "Try creating a new session"
            ],
            context={
                "session_id": session_id,
                "error_type": type(e).__name__
            },
            next_steps="Review the error and retry the operation."
        )
