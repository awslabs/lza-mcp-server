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

"""Component registration for MCP server."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_core_tools(mcp: Any) -> None:
    """Register core MCP tools.

    Args:
        mcp: FastMCP server instance
    """
    from .tools.aws_services import register_aws_tools
    from .tools.config import register_config_tools
    from .tools.pipeline import register_pipeline_tools
    from .tools.schema import register_schema_tools

    register_aws_tools(mcp)
    register_config_tools(mcp)
    register_pipeline_tools(mcp)
    register_schema_tools(mcp)


def register_uc_merge_tools_if_enabled(mcp: Any, enabled: bool) -> None:
    """Conditionally register UC Merge tools.

    Args:
        mcp: FastMCP server instance
        enabled: Whether UC Merge tools should be enabled
    """
    if enabled:
        from .tools.uc_merge import register_uc_merge_tools

        register_uc_merge_tools(mcp)
        logger.info("UC Merge tools enabled and registered")
    else:
        logger.info("UC Merge tools disabled (set ENABLE_UC_MERGE=true to enable)")


def register_all_components(mcp: Any, enable_uc_merge: bool) -> None:
    """Register all MCP tools and resources.

    Args:
        mcp: FastMCP server instance
        enable_uc_merge: Whether to enable UC Merge tools
    """
    register_core_tools(mcp)
    register_uc_merge_tools_if_enabled(mcp, enable_uc_merge)
    logger.info("All MCP components registered successfully")
