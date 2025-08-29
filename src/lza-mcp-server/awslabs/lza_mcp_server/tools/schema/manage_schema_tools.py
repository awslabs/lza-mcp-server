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

"""Schema-related MCP tools for the LZA MCP Server."""

import logging
from typing import Dict, Any, List, Optional

from mcp.server.fastmcp import Context

from .get_full_schema import tool_search_json_schema
from .search_json_schema import tool_get_full_schema

logger = logging.getLogger(__name__)


def register_schema_tools(mcp):
    """Register schema-related MCP tools."""

    @mcp.tool(name="searchJsonSchema")  # nosemgrep: useless-inner-function
    async def search_json_schema(
        ctx: Context,
        search_terms: List[str],
        search_type: str = "general",
        max_results: int = 10,
        include_metadata: bool = True,
        include_schema: bool = False,
        filters: Optional[Dict] = None,
        schema_path: Optional[str] = None,
        format_level: str = "standard",
    ) -> Dict[str, Any]:
        return await tool_search_json_schema(
            ctx,
            search_terms,
            search_type,
            max_results,
            include_metadata,
            include_schema,
            filters,
            schema_path,
            format_level,
        )

    @mcp.tool(name="getFullSchema")  # nosemgrep: useless-inner-function
    async def get_full_schema(
        ctx: Context,
        schema_path: str,
        property_path: Optional[str] = None,
        include_metadata: bool = True,
    ) -> Dict[str, Any]:
        return await tool_get_full_schema(
            ctx,
            schema_path,
            property_path,
            include_metadata,
        )

    logger.info("Schema tools registered successfully")
