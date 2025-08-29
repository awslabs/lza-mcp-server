from typing import Optional

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
from typing import Dict, Any
from mcp.server.fastmcp import Context


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
    schema_path: str, target_schema: Dict[str, Any], include_metadata: bool
) -> Dict[str, Any]:
    """Build the result dictionary for a full schema."""
    result = {
        "success": True,
        "schema_path": schema_path,
    }

    if include_metadata and "_metadata" in target_schema:
        result["metadata"] = target_schema["_metadata"]

    schema_copy = {k: v for k, v in target_schema.items() if k != "_metadata"}
    result["schema"] = schema_copy

    return result


async def tool_get_full_schema(
    ctx: Context,
    schema_path: str,
    property_path: Optional[str] = None,
    include_metadata: bool = True,
) -> Dict[str, Any]:
    """Retrieve the full details of a JSON schema or a specific property within it.

    This tool retrieves complete schema information for detailed analysis. It's typically
    used after finding schemas with searchJsonSchema when you need to examine the full
    structure or a specific property within a schema.

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
        schema_path (str): The path to the schema (returned by searchJsonSchema as 'schema_ref')
        property_path (str, optional): Optional path to a specific property within the schema (extracted from searchJsonSchema match_locations)
        include_metadata (bool, optional): Whether to include metadata in the result. Default: True

    Returns:
        Complete schema or specific property details with optional metadata
    """
    try:
        await ctx.info(f"Retrieving schema: {schema_path}")
        if property_path:
            await ctx.info(f"Looking for specific property path: {property_path}")

        combined_schema_path = os.path.join("/app/json-output", "combined.json")

        if not os.path.exists(combined_schema_path):
            error_message = f"Combined schema file not found at: {combined_schema_path}"
            await ctx.error(error_message)
            return {
                "success": False,
                "error": error_message,
                "message": "Combined schema file not found. The file is generated by the docker-json-schema.sh script during container startup.",
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

        return _build_full_schema_result(schema_path, target_schema, include_metadata)

    except Exception as e:
        await ctx.error(f"Unexpected error: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "An unexpected error occurred while processing the schema request.",
        }
