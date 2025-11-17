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

import os
from typing import Dict, Any, List
from mcp.server.fastmcp import Context


async def tool_list_lza_supported_versions(ctx: Context) -> Dict[str, Any]:
    """List all supported LZA versions with their schema information.

    This tool helps discover which LZA versions are available for schema searches.
    It scans the json-schemas directory and returns information about each version,
    including whether the combined.json file exists and is accessible.

    Returns:
        Dictionary containing list of available versions with their status and metadata
    """
    try:
        await ctx.info("Listing available LZA versions")

        schemas_base = "/app/json-schemas"
        
        if not os.path.exists(schemas_base):
            return {
                "success": False,
                "error": "Schemas directory not found",
                "message": f"The schemas directory does not exist at: {schemas_base}",
                "hint": "Ensure the Docker container has been built with the download-lza-versions.sh script",
            }

        # Get all directories in the schemas base
        try:
            all_items = os.listdir(schemas_base)
            version_dirs = [
                item for item in all_items 
                if os.path.isdir(os.path.join(schemas_base, item))
            ]
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to list schemas directory: {str(e)}",
                "message": "Could not read the schemas directory",
            }

        if not version_dirs:
            return {
                "success": True,
                "message": "No LZA versions found",
                "versions": [],
                "hint": "The schemas directory exists but contains no version subdirectories",
            }

        # Collect information about each version
        versions_info: List[Dict[str, Any]] = []
        latest_version = None

        for version_dir in sorted(version_dirs):
            version_path = os.path.join(schemas_base, version_dir)
            combined_json_path = os.path.join(version_path, "combined.json")
            
            # Check if this is a symlink (likely the 'latest' link)
            is_symlink = os.path.islink(version_path)
            
            # Get symlink target if applicable
            symlink_target = None
            if is_symlink:
                try:
                    symlink_target = os.readlink(version_path)
                    if version_dir == "latest":
                        latest_version = symlink_target
                except Exception:
                    pass

            # Check if combined.json exists
            has_combined_json = os.path.exists(combined_json_path)
            
            # Get file size if it exists
            file_size_mb = None
            if has_combined_json:
                try:
                    file_size = os.path.getsize(combined_json_path)
                    file_size_mb = round(file_size / (1024 * 1024), 2)
                except Exception:
                    pass

            version_info = {
                "version": version_dir,
                "is_symlink": is_symlink,
                "has_schemas": has_combined_json,
                "status": "ready" if has_combined_json else "incomplete",
            }

            if symlink_target:
                version_info["symlink_target"] = symlink_target
            
            if file_size_mb is not None:
                version_info["schema_size_mb"] = file_size_mb

            versions_info.append(version_info)

        # Sort versions: put 'latest' first, then sort others
        versions_info.sort(key=lambda x: (x["version"] != "latest", x["version"]), reverse=False)

        return {
            "success": True,
            "message": f"Found {len(versions_info)} LZA version(s)",
            "versions": versions_info,
            "latest_version": latest_version,
            "schemas_directory": schemas_base,
            "usage_hint": "Use the 'version' field value as the lza_version parameter in searchJsonSchema and getFullSchema",
        }

    except Exception as e:
        error_message = f"Error listing LZA versions: {str(e)}"
        await ctx.error(error_message)
        return {
            "success": False,
            "error": error_message,
            "message": "An unexpected error occurred while listing versions",
        }
