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

"""Get available UC release versions."""

import os
import logging
from pathlib import Path
from typing import Dict, Any, List
from mcp.server.fastmcp import Context

logger = logging.getLogger(__name__)


def _parse_version(version_str: str) -> tuple:
    """Parse version string into tuple for sorting.
    
    Args:
        version_str: Version string like "v1.0.0" or "1.0.0"
        
    Returns:
        Tuple of integers for comparison
    """
    # Remove 'v' prefix if present
    version_str = version_str.lstrip('v')
    
    try:
        parts = version_str.split('.')
        return tuple(int(p) for p in parts)
    except (ValueError, AttributeError):
        # If parsing fails, return a tuple that sorts to the end
        return (0, 0, 0)


async def tool_get_uc_releases(ctx: Context) -> Dict[str, Any]:
    """Discover available UC release versions.
    
    Scans the UC repository directory to find all available release versions
    of the AWS Landing Zone Accelerator Universal Configuration. Returns
    releases in descending version order (newest first) to help users select
    the most appropriate version for their deployment.
    
    The Universal Configuration provides enterprise-ready templates that
    establish secure, scalable, and well-architected multi-account AWS
    environments with support for multiple global compliance frameworks.
    
    Returns:
        Dictionary containing:
        - success (bool): Operation success status
        - releases (List[Dict]): List of available releases with name and path
        - uc_base_path (str): Base path to UC repository
        - next_steps (str): Guidance for presenting releases to user
        
    Example:
        ```python
        result = await get_uc_releases()
        
        if result["success"]:
            print(f"Available UC releases: {len(result['releases'])}")
            for release in result["releases"]:
                print(f"  - {release['name']} at {release['path']}")
            
            # Present to user and request selection
            print(result["next_steps"])
        ```
    """
    await ctx.info("Discovering available UC release versions")
    
    # Get UC base path from environment or use default
    uc_base_path = os.environ.get("LZA_UC_BASE_PATH", "/app/lza-uc")
    
    try:
        uc_path = Path(uc_base_path)
        
        # Check if UC directory exists
        if not uc_path.exists():
            error_msg = f"UC repository directory not found: {uc_base_path}"
            await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "error_code": "UC_DIRECTORY_NOT_FOUND",
                "troubleshooting": [
                    "Verify the UC repository is mounted in the container",
                    "Check that LZA_UC_BASE_PATH environment variable is set correctly",
                    "Ensure the Docker container has access to the UC files"
                ],
                "next_steps": "Contact administrator to verify UC repository installation"
            }
        
        if not uc_path.is_dir():
            error_msg = f"UC repository path is not a directory: {uc_base_path}"
            await ctx.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "error_code": "UC_PATH_NOT_DIRECTORY",
                "troubleshooting": [
                    "Verify the UC repository path points to a directory",
                    "Check file system permissions"
                ],
                "next_steps": "Contact administrator to verify UC repository installation"
            }
        
        # Scan for release directories
        releases: List[Dict[str, str]] = []
        
        for item in uc_path.iterdir():
            if item.is_dir():
                release_name = item.name
                release_path = str(item)
                
                releases.append({
                    "name": release_name,
                    "path": release_path
                })
                
                await ctx.info(f"Found UC release: {release_name}")
        
        # Sort releases in descending version order (newest first)
        releases.sort(key=lambda r: _parse_version(r["name"]), reverse=True)
        
        if not releases:
            await ctx.info(f"No UC releases found in {uc_base_path}")
            return {
                "success": True,
                "releases": [],
                "uc_base_path": uc_base_path,
                "next_steps": "No UC releases are currently available. Contact administrator to install UC releases."
            }
        
        await ctx.info(f"Discovered {len(releases)} UC release(s)")
        
        # Build release list for presentation
        release_names = [r["name"] for r in releases]
        release_list = "\n".join([f"  - {name}" for name in release_names])
        
        return {
            "success": True,
            "releases": releases,
            "uc_base_path": uc_base_path,
            "next_steps": (
                f"Present the following UC releases to the user and request their selection:\n\n"
                f"Available UC releases (newest first):\n{release_list}\n\n"
                f"After the user selects a release, call get_uc_network_models() with the "
                f"selected uc_release parameter to discover available network deployment models."
            )
        }
        
    except PermissionError as e:
        error_msg = f"Permission denied accessing UC repository: {str(e)}"
        await ctx.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "error_code": "PERMISSION_DENIED",
            "troubleshooting": [
                "Check file system permissions for UC repository",
                "Verify the container has read access to the UC directory"
            ],
            "next_steps": "Contact administrator to verify UC repository permissions"
        }
    except Exception as e:
        error_msg = f"Unexpected error discovering UC releases: {str(e)}"
        await ctx.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "error_code": "UNEXPECTED_ERROR",
            "troubleshooting": [
                "Check system logs for detailed error information",
                "Verify UC repository structure is intact"
            ],
            "next_steps": "Contact administrator for assistance"
        }
