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
import json
from typing import Dict, Any, Optional
from mcp.server.fastmcp import Context
from awslabs.lza_mcp_server.utils.input_validation import (
    validate_string_input,
    validate_json_schema_path,
    validate_lza_version,
)


def _load_combined_schemas(combined_schema_path: str) -> Dict[str, Any]:
    """Load and return the combined schemas from file."""
    with open(combined_schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _navigate_to_property(
    schema_content: Dict[str, Any], property_path: str
) -> Dict[str, Any]:
    """Navigate to a specific property within the schema."""
    current_node = schema_content
    path_parts = property_path.split(".")
    navigation_history = []

    for i, part in enumerate(path_parts):
        base_part = part.split("[")[0] if "[" in part else part
        navigation_history.append(base_part)

        if base_part in current_node:
            current_node = current_node[base_part]
            if "[" in part and isinstance(current_node, list) and current_node:
                if i == len(path_parts) - 1 or (
                    i < len(path_parts) - 1 and "[" in path_parts[i + 1]
                ):
                    pass
                else:
                    current_node = current_node[0]
        elif current_node.get("properties") and base_part in current_node["properties"]:
            current_node = current_node["properties"][base_part]
        elif (
            current_node.get("items")
            and isinstance(current_node["items"], dict)
            and base_part in current_node["items"]
        ):
            current_node = current_node["items"][base_part]
        else:
            available_props = []
            if isinstance(current_node, dict):
                available_props = list(current_node.keys())
                if "properties" in current_node and isinstance(
                    current_node["properties"], dict
                ):
                    available_props += list(current_node["properties"].keys())

            raise ValueError(
                f"Property path element '{base_part}' not found at '{'.'.join(navigation_history)}'. Available: {available_props[:10]}"
            )

    return current_node


def _build_property_result(
    schema_path: str,
    property_path: str,
    property_node: Any,
    target_schema: Dict[str, Any],
    include_metadata: bool,
) -> Dict[str, Any]:
    """Build the result dictionary for a specific property."""
    result = {
        "success": True,
        "schema_path": schema_path,
        "property_path": property_path,
        "property": property_node,
    }

    if include_metadata and "_metadata" in target_schema:
        result["schema_metadata"] = target_schema["_metadata"]

    return result


def _build_full_schema_result(
    schema_path: str,
    target_schema: Dict[str, Any],
    include_metadata: bool,
    lza_version: str,
) -> Dict[str, Any]:
    """Build the result dictionary for a full schema."""
    result = {
        "success": True,
        "lza_version": lza_version,
        "schema_path": schema_path,
    }

    if include_metadata and "_metadata" in target_schema:
        result["metadata"] = target_schema["_metadata"]

    schema_copy = {k: v for k, v in target_schema.items() if k != "_metadata"}
    result["schema"] = schema_copy

    return result


async def tool_get_full_schema(
    ctx: Context,
    lza_version: str,
    schema_path: str,
    property_path: Optional[str] = None,
    include_metadata: bool = True,
) -> Dict[str, Any]:
    """Retrieve the full details of a JSON schema or a specific property within it.

    This tool retrieves complete schema information for detailed analysis. It's typically
    used after finding schemas with searchJsonSchema when you need to examine the full
    structure or a specific property within a schema.

    RECOMMENDED WORKFLOW: Call getDeployedLzaVersion() first to get the correct lza_version
    parameter that matches your deployed environment.

    The tool can return:
    - Complete schema definitions with all properties and constraints
    - Specific property details when a property path is provided
    - Schema metadata including statistics and relationships

    Property paths can be extracted from searchJsonSchema results' match_locations field.
    For example, if a match location shows "property:centralNetworkServices.ipams:substring",
    you can use "centralNetworkServices.ipams" as the property_path to get just that
    section of the schema.

    This enables efficient exploration of large schemas by focusing on relevant sections.

    Args:
        lza_version (str): LZA version to use (e.g., 'v1.12.0', 'v1.13.0'). Call getDeployedLzaVersion() to get the correct version.
        schema_path (str): The path to the schema (returned by searchJsonSchema as 'schema_ref')
        property_path (str, optional): Optional path to a specific property within the schema (extracted from searchJsonSchema match_locations)
        include_metadata (bool, optional): Whether to include metadata in the result. Default: True

    Returns:
        Complete schema or specific property details with optional metadata
    """
    try:
        # Validate LZA version parameter
        is_valid, validation_error = validate_string_input(
            lza_version, "lza_version", min_length=1, max_length=50
        )
        if not is_valid:
            await ctx.error(validation_error)
            return {
                "success": False,
                "error": validation_error,
                "message": "Invalid LZA version format",
                "hint": "Call getDeployedLzaVersion() first to get the correct version. For example, if it returns 'v1.12.0', use lza_version='v1.12.0'",
            }

        if not lza_version:
            error_message = "lza_version parameter is required"
            await ctx.error(error_message)
            return {
                "success": False,
                "error": error_message,
                "message": "Please specify an LZA version (e.g., 'v1.12.0', 'v1.13.0')",
                "hint": "Call getDeployedLzaVersion() first to get the correct version. For example, if it returns 'v1.12.0', use lza_version='v1.12.0'",
            }

        # Validate LZA version format (prevents path traversal via version parameter)
        # Security validation runs before business logic checks like "latest" rejection
        is_valid, validation_error = validate_lza_version(lza_version)
        if not is_valid:
            await ctx.error(validation_error)
            return {
                "success": False,
                "error": validation_error,
                "message": "Invalid LZA version format",
                "hint": "Call getDeployedLzaVersion() first to get the correct version. For example, if it returns 'v1.12.0', use lza_version='v1.12.0'",
            }

        # Validate schema_path parameter
        is_valid, validation_error = validate_json_schema_path(schema_path)
        if not is_valid:
            await ctx.error(validation_error)
            return {
                "success": False,
                "error": validation_error,
                "message": "Invalid schema path format",
            }

        # Validate property_path if provided
        if property_path:
            is_valid, validation_error = validate_string_input(
                property_path, "property_path", min_length=1, max_length=500
            )
            if not is_valid:
                await ctx.error(validation_error)
                return {
                    "success": False,
                    "error": validation_error,
                    "message": "Invalid property path format",
                }

        await ctx.info(f"Retrieving schema (version: {lza_version}): {schema_path}")
        if property_path:
            await ctx.info(f"Looking for specific property path: {property_path}")

        # Use version-specific path
        schemas_base = os.environ.get("LZA_SCHEMA_DIR", "/app/json-schemas")
        combined_schema_path = os.path.join(schemas_base, lza_version, "combined.json")

        if not os.path.exists(combined_schema_path):
            # Check if version directory exists to provide better error message
            version_dir = os.path.join(schemas_base, lza_version)
            if not os.path.exists(version_dir):
                available_versions = []
                if os.path.exists(schemas_base):
                    available_versions = [
                        d
                        for d in os.listdir(schemas_base)
                        if os.path.isdir(os.path.join(schemas_base, d))
                    ]

                error_message = "LZA version not found"
                await ctx.error(error_message)
                return {
                    "success": False,
                    "error": error_message,
                    "message": "The specified LZA version is not available.",
                    "available_versions": available_versions
                    if available_versions
                    else ["No versions found"],
                    "hint": "Call getDeployedLzaVersion() to get the correct version, or use listLzaSupportedVersions() to see all available versions",
                }
            else:
                error_message = "Schema file not found for the specified version"
                await ctx.error(error_message)
                return {
                    "success": False,
                    "error": error_message,
                    "message": "Version directory exists but combined.json not found",
                }

        try:
            combined_schemas = _load_combined_schemas(combined_schema_path)
            await ctx.info(
                f"Loaded combined schema file with {len(combined_schemas)} schemas"
            )
        except Exception as e:
            error_message = f"Failed to load combined schema file: {str(e)}"
            await ctx.error(error_message)
            return {
                "success": False,
                "error": error_message,
                "message": "Error loading combined schema file.",
            }

        if schema_path not in combined_schemas:
            error_message = f"Schema not found: {schema_path}"
            await ctx.error(error_message)
            available_schemas = list(combined_schemas.keys())[:5]
            return {
                "success": False,
                "error": error_message,
                "message": "The requested schema could not be found in the combined schema file.",
                "available_schemas_sample": available_schemas,
            }

        target_schema = combined_schemas[schema_path]

        if property_path:
            try:
                schema_content = {
                    k: v for k, v in target_schema.items() if k != "_metadata"
                }
                property_node = _navigate_to_property(schema_content, property_path)
                return _build_property_result(
                    schema_path,
                    property_path,
                    property_node,
                    target_schema,
                    include_metadata,
                )
            except ValueError as e:
                await ctx.error(str(e))
                return {
                    "success": False,
                    "error": str(e),
                    "message": f"Could not navigate to '{property_path}'.",
                }
            except Exception as e:
                error_message = f"Error navigating to property path: {str(e)}"
                await ctx.error(error_message)
                return {
                    "success": False,
                    "error": error_message,
                    "message": f"The property path '{property_path}' could not be processed.",
                }

        return _build_full_schema_result(
            schema_path, target_schema, include_metadata, lza_version
        )

    except Exception as e:
        await ctx.error(f"Unexpected error: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "An unexpected error occurred while processing the schema request.",
        }
